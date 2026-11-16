"""
Merge a fresh SyncResult into a provider's existing catalog files (design D4, D7).

Rules:
  - new record            → added, first_seen = updated_at = today
  - unchanged record      → kept byte-for-byte (no date churn)
  - changed record        → updated_at = today; provenance.as_of = today
  - None / [] incoming    → keep the existing value ("empty means unknown", never erase known data)
  - missing upstream      → kept, marked deprecated (lifecycle + deprecated_at for models)
  - deprecated, reappears → revived
  - guard                 → refuse if a section would lose too much (empty fetch, partial fetch)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from naaviq.catalog.files import ProviderData
from naaviq.catalog.schema import (
    STT_CAPABILITIES,
    TTS_CAPABILITIES,
    Model,
    Provenance,
    Provider,
    Voice,
)
from naaviq.sync.base import SyncModel, SyncResult, SyncVoice

SHRINK_LIMIT = 0.25         # max share of active records a single sync may deprecate
SHRINK_MIN_ACTIVE = 4       # below this many active records the ratio guard is too noisy

# Fields that describe bookkeeping, not content — ignored when deciding "did it change?"
_BOOKKEEPING = {"first_seen", "updated_at", "deprecated_at", "provenance"}


class GuardError(Exception):
    """Raised when a sync looks like a partial/broken fetch. Re-run with allow_shrink to override."""


@dataclass
class Change:
    kind: str                  # "added" | "updated" | "deprecated" | "revived"
    section: str               # "stt" | "tts" | "sts" | "voices"
    key: str
    fields: dict[str, tuple[Any, Any]] = field(default_factory=dict)


@dataclass
class MergeReport:
    changes: list[Change] = field(default_factory=list)

    def counts(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for c in self.changes:
            out.setdefault(c.section, {}).setdefault(c.kind, 0)
            out[c.section][c.kind] += 1
        return out

    @property
    def has_changes(self) -> bool:
        return bool(self.changes)


# ── SyncResult → v2 records ───────────────────────────────────────────────────

def _provenance_for(source: str | None, result: SyncResult, today: date) -> Provenance:
    method = source or ("docs" if result.source == "docs" else "api")
    urls = result.docs_urls if method == "docs" else result.api_urls
    return Provenance(method=method, urls=list(urls), as_of=today)


def model_from_sync(m: SyncModel, result: SyncResult, today: date) -> Model:
    meta = dict(m.meta or {})
    family = meta.pop("parent_model_id", None) or meta.pop("family", None)
    snapshot_date = meta.pop("snapshot_date", None)
    meta.pop("is_snapshot", None)
    alias_of = meta.pop("alias_of", None)
    batch = meta.pop("batch", None)

    # Drop terms that belong to the *other* modality (e.g. "emotion" on an STT model), which AI
    # extraction occasionally emits. Unknown terms are left in so schema validation rejects them.
    caps = list(m.capabilities or [])
    wrong_modality = {"stt": TTS_CAPABILITIES - STT_CAPABILITIES, "tts": STT_CAPABILITIES - TTS_CAPABILITIES}
    caps = [c for c in caps if c not in wrong_modality.get(m.type, frozenset())]

    return Model(
        id=m.model_id,
        type=m.type,
        name=m.display_name,
        description=m.description,
        family=family,
        alias_of=alias_of,
        snapshot_date=snapshot_date,
        lifecycle=m.lifecycle,
        is_default=m.is_default,
        languages=m.languages,
        streaming=m.streaming,
        batch=batch if isinstance(batch, bool) else None,
        interfaces=m.interfaces,
        sample_rates_hz=m.sample_rates_hz,
        audio_formats=m.audio_formats,
        max_text_chars=m.max_text_chars,
        max_audio_seconds=m.max_audio_seconds,
        capabilities=caps,
        regions=m.regions,
        pricing=m.pricing or None,
        open_weights=m.open_weights,
        eol_date=m.eol_date,
        meta={k: v for k, v in meta.items() if v is not None},
        provenance=_provenance_for(m.source, result, today),
    )


def voice_from_sync(v: SyncVoice) -> Voice:
    return Voice(
        id=v.voice_id,
        name=v.display_name,
        gender=v.gender,
        age=v.age,
        category=v.category,
        description=v.description,
        languages=v.languages,
        accent=v.accent,
        compatible_models=v.compatible_models,
        capabilities=v.capabilities,
        preview_url=v.preview_url,
        use_cases=v.use_cases,
        tags=v.tags,
        meta={k: val for k, val in (v.meta or {}).items() if val is not None},
    )


# ── Merge ─────────────────────────────────────────────────────────────────────

def _content(rec) -> dict:
    return rec.model_dump(mode="json", exclude=_BOOKKEEPING)


def _fill_unknowns(incoming: dict, existing: dict) -> dict:
    """D7: an empty/None incoming value means 'unknown' — keep what we already know."""
    out = dict(incoming)
    for k, old in existing.items():
        if k in _BOOKKEEPING or k in ("is_default", "streaming", "lifecycle"):
            continue
        if out.get(k) in (None, [], {}, "") and old not in (None, [], {}, ""):
            out[k] = old
    return out


def _diff(old: dict, new: dict) -> dict[str, tuple[Any, Any]]:
    return {k: (old.get(k), new.get(k)) for k in sorted(set(old) | set(new)) if old.get(k) != new.get(k)}


def _merge_section(
    section: str,
    existing: list,
    incoming: list,
    cls,
    today: date,
    report: MergeReport,
    deprecate_fields: dict,
    allow_shrink: bool,
) -> list:
    old_by_id = {r.id: r for r in existing}
    new_ids = {r.id for r in incoming}
    out = []

    for rec in incoming:
        prev = old_by_id.get(rec.id)
        if prev is None:
            out.append(rec.model_copy(update={"first_seen": today, "updated_at": today}))
            report.changes.append(Change("added", section, rec.id))
            continue

        merged_content = _fill_unknowns(_content(rec), _content(prev))
        was_deprecated = prev.deprecated_at is not None
        changes = _diff(_content(prev), merged_content)
        if not changes and not was_deprecated:
            out.append(prev)  # unchanged — keep bookkeeping as-is
            continue

        update: dict[str, Any] = {"first_seen": prev.first_seen or today, "updated_at": today, "deprecated_at": None}
        if getattr(rec, "provenance", None) is not None:
            update["provenance"] = rec.provenance
        out.append(cls.model_validate({**merged_content, **update}))
        report.changes.append(Change("revived" if was_deprecated else "updated", section, rec.id, changes))

    active_old = [r for r in existing if r.deprecated_at is None]
    to_deprecate = [r for r in active_old if r.id not in new_ids]
    if not allow_shrink:
        if active_old and not incoming:
            raise GuardError(f"{section}: upstream returned nothing but {len(active_old)} active records exist")
        if len(active_old) >= SHRINK_MIN_ACTIVE and len(to_deprecate) / len(active_old) > SHRINK_LIMIT:
            raise GuardError(
                f"{section}: would deprecate {len(to_deprecate)}/{len(active_old)} active records "
                f"(> {SHRINK_LIMIT:.0%}) — looks like a partial fetch"
            )

    for r in existing:
        if r.id in new_ids:
            continue
        if r.deprecated_at is None:
            out.append(r.model_copy(update={"deprecated_at": today, "updated_at": today, **deprecate_fields}))
            report.changes.append(Change("deprecated", section, r.id))
        else:
            out.append(r)
    return out


def derive_provider_type(models: list[Model]) -> str | None:
    types = {m.type for m in models if m.deprecated_at is None}
    if not types:
        return None
    if types == {"stt"}:
        return "stt"
    if types <= {"tts"}:
        return "tts"
    if types == {"sts"}:
        return "sts"
    return "both"


def merge(
    current: ProviderData | None,
    result: SyncResult,
    *,
    provider_id: str,
    display_name: str,
    seeded_type: str,
    today: date,
    allow_shrink: bool = False,
) -> tuple[ProviderData, MergeReport]:
    report = MergeReport()
    current = current or ProviderData(Provider(id=provider_id, name=display_name, type=seeded_type))

    incoming_models = [model_from_sync(m, result, today) for m in result.stt_models + result.tts_models]
    incoming_models += [model_from_sync(m, result, today) for m in result.sts_models]
    incoming_voices = [voice_from_sync(v) for v in result.tts_voices]

    _check_unique(incoming_models, key=lambda m: (m.type, m.id), what="model")
    _check_unique(incoming_voices, key=lambda v: v.id, what="voice")
    _check_single_default(incoming_models)

    models: list[Model] = []
    for t in ("stt", "tts", "sts"):
        models += _merge_section(
            t,
            [m for m in current.models if m.type == t],
            [m for m in incoming_models if m.type == t],
            Model, today, report,
            deprecate_fields={"lifecycle": "deprecated", "is_default": False},
            allow_shrink=allow_shrink,
        )
    voices = _merge_section(
        "voices", current.voices, incoming_voices, Voice, today, report,
        deprecate_fields={}, allow_shrink=allow_shrink,
    )

    p = current.provider
    voices_method = "docs" if result.source == "docs" else "api"
    provider = p.model_copy(update={
        "type": derive_provider_type(models) or p.type,
        "source": result.source,
        "api_urls": result.api_urls or p.api_urls,
        "docs_urls": result.docs_urls or p.docs_urls,
        "voices_source": (
            Provenance(method=voices_method,
                       urls=result.api_urls if voices_method == "api" else result.docs_urls,
                       as_of=today)
            if result.tts_voices else p.voices_source
        ),
        "last_synced": today,
    })
    return ProviderData(Provider.model_validate(provider.model_dump()), models, voices), report


def _check_unique(records: list, key, what: str) -> None:
    seen: set = set()
    dupes = sorted({str(key(r)) for r in records if key(r) in seen or seen.add(key(r))})
    if dupes:
        raise ValueError(f"duplicate {what} ids in sync result: {dupes}")


def _check_single_default(models: list[Model]) -> None:
    for t in ("stt", "tts", "sts"):
        defaults = [m.id for m in models if m.type == t and m.is_default]
        if len(defaults) > 1:
            raise ValueError(f"more than one default {t} model: {defaults}")
