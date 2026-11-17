"""Shared query validation and in-memory filtering for model/voice list endpoints."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime

from fastapi import HTTPException, Request

from voicedex.catalog.schema import MODEL_CAPABILITIES, VOICE_CAPABILITIES, Lifecycle, Region
from voicedex.catalog.store import Catalog, ModelRow, VoiceRow, language_matches

VALID_LIFECYCLES = {e.value for e in Lifecycle}
VALID_REGIONS = {e.value for e in Region}
VALID_MODEL_TYPES = {"stt", "tts", "sts"}
VALID_GENDERS = {"male", "female", "neutral"}
VALID_CATEGORIES = {"premade", "cloned", "generated"}

UPDATED_SINCE_DESC = (
    "ISO-8601 date or timestamp; returns rows whose updated_at date is on/after this day. "
    "When set, deprecated rows are included by default so polling consumers see deprecations; "
    "pass include_deprecated=false to override."
)


def get_catalog(request: Request) -> Catalog:
    return request.app.state.catalog


def _csv(raw: str | None) -> list[str]:
    return [p.strip() for p in raw.split(",") if p.strip()] if raw else []


def _enum(raw: str | None, valid: set[str], name: str) -> str | None:
    if raw is None or raw == "":
        return None
    val = raw.strip().lower()
    if val not in valid:
        raise HTTPException(400, f"Invalid {name}: {raw!r}. Allowed: {sorted(valid)}")
    return val


def parse_capabilities(raw: str | None, valid: frozenset[str], kind: str) -> list[str]:
    parts = _csv(raw)
    bad = [p for p in parts if p not in valid]
    if bad:
        raise HTTPException(400, f"Invalid {kind} capability: {bad}. Allowed: {sorted(valid)}")
    return parts


def parse_lifecycles(raw: str | None) -> list[str]:
    parts = _csv(raw)
    bad = [p for p in parts if p not in VALID_LIFECYCLES]
    if bad:
        raise HTTPException(400, f"Invalid lifecycle value(s): {bad}. Allowed: {sorted(VALID_LIFECYCLES)}")
    return parts


def validate_region(raw: str | None) -> str | None:
    return _enum(raw, VALID_REGIONS, "region")


def effective_include_deprecated(include_deprecated: bool | None, updated_since: datetime | None) -> bool:
    if include_deprecated is not None:
        return include_deprecated
    return updated_since is not None


def _since(updated_since: datetime | None) -> date | None:
    return updated_since.date() if updated_since else None


def filter_models(
    rows: Iterable[ModelRow],
    *,
    provider: str | None = None,
    model_type: str | None = None,
    language: str | None = None,
    capabilities: str | None = None,
    lifecycle: str | None = None,
    region: str | None = None,
    search: str | None = None,
    updated_since: datetime | None = None,
    include_deprecated: bool | None = None,
) -> list[ModelRow]:
    mtype = _enum(model_type, VALID_MODEL_TYPES, "type")
    caps = set(parse_capabilities(capabilities, MODEL_CAPABILITIES, "model"))
    stages = set(parse_lifecycles(lifecycle))
    region_val = validate_region(region)
    incl_dep = effective_include_deprecated(include_deprecated, updated_since)
    since = _since(updated_since)
    needle = search.strip().lower() if search else None

    out = []
    for r in rows:
        m = r.model
        if provider and r.provider_id != provider:
            continue
        if not incl_dep and m.deprecated_at is not None:
            continue
        if mtype and m.type != mtype:
            continue
        if language and not language_matches(language, m.languages):
            continue
        if caps and not caps <= set(m.capabilities):
            continue
        if stages and m.lifecycle not in stages:
            continue
        if region_val and region_val not in m.regions and "global" not in m.regions:
            continue
        if needle and needle not in m.name.lower() and needle not in m.id.lower() \
                and needle not in (m.description or "").lower():
            continue
        if since and (m.updated_at is None or m.updated_at < since):
            continue
        out.append(r)
    return out


def filter_voices(
    rows: Iterable[VoiceRow],
    *,
    provider: str | None = None,
    gender: str | None = None,
    category: str | None = None,
    language: str | None = None,
    model: str | None = None,
    accent: str | None = None,
    capabilities: str | None = None,
    search: str | None = None,
    updated_since: datetime | None = None,
    include_deprecated: bool | None = None,
) -> list[VoiceRow]:
    gender_val = _enum(gender, VALID_GENDERS, "gender")
    category_val = _enum(category, VALID_CATEGORIES, "category")
    caps = set(parse_capabilities(capabilities, VOICE_CAPABILITIES, "voice"))
    incl_dep = effective_include_deprecated(include_deprecated, updated_since)
    since = _since(updated_since)
    accent_val = accent.strip().lower() if accent else None
    needle = search.strip().lower() if search else None

    out = []
    for r in rows:
        v = r.voice
        if provider and r.provider_id != provider:
            continue
        if not incl_dep and v.deprecated_at is not None:
            continue
        if gender_val and v.gender != gender_val:
            continue
        if category_val and v.category != category_val:
            continue
        if language and not language_matches(language, v.languages):
            continue
        if model and model not in v.compatible_models and "*" not in v.compatible_models:
            continue
        if accent_val and v.accent != accent_val:
            continue
        if caps and not caps <= set(v.capabilities):
            continue
        if needle and needle not in v.name.lower() and needle not in v.id.lower() \
                and not any(needle in t.lower() for t in v.tags) \
                and needle not in (v.description or "").lower():
            continue
        if since and (v.updated_at is None or v.updated_at < since):
            continue
        out.append(r)
    return out


def sort_models(rows: list[ModelRow], cross_provider: bool) -> list[ModelRow]:
    key = (lambda r: (r.provider_id, r.model.name.lower(), r.model.id)) if cross_provider \
        else (lambda r: (r.model.name.lower(), r.model.id))
    return sorted(rows, key=key)


def sort_voices(rows: list[VoiceRow], cross_provider: bool) -> list[VoiceRow]:
    key = (lambda r: (r.provider_id, r.voice.name.lower(), r.voice.id)) if cross_provider \
        else (lambda r: (r.voice.name.lower(), r.voice.id))
    return sorted(rows, key=key)
