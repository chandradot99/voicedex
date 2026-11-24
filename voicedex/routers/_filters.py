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

OPEN_WEIGHTS_DESC = "true = only models with downloadable weights (open_weights set); false = only hosted-only models."

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


def _enum_ci(raw: str | None, valid: list[str], name: str) -> str | None:
    """Case-insensitive match against labels like "Audiobooks & stories"; returns the canonical label."""
    if not raw:
        return None
    hit = next((v for v in valid if v.lower() == raw.strip().lower()), None)
    if hit is None:
        raise HTTPException(400, f"Invalid {name}: {raw!r}. Allowed: {valid}")
    return hit


FRAMEWORK_DESC = ("livekit, pipecat, vapi, retell: only models whose provider has a first-party integration "
                  "for that model type in the framework's own docs.")


def filter_framework(rows, framework: str | None, catalog: Catalog):
    """Keep rows whose provider the framework integrates for that model type (provider-level, per type)."""
    from voicedex.catalog.schema import FRAMEWORKS
    from voicedex.web import views
    if not framework:
        return rows
    fw = framework.strip().lower()
    if fw not in FRAMEWORKS:
        raise HTTPException(400, f"Invalid framework: {framework!r}. Allowed: {list(FRAMEWORKS)}")
    return [r for r in rows if fw in views.model_frameworks(catalog, r)]


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
    open_weights: bool | None = None,
    realtime: bool | None = None,
    recommended: bool | None = None,
    shutting_down: bool | None = None,
    max_price_usd: float | None = None,
) -> list[ModelRow]:
    from voicedex.web import views
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
        if open_weights is not None and (m.open_weights is not None) != open_weights:
            continue
        if realtime is not None and views.is_realtime(m) != realtime:
            continue
        if recommended is not None and (m.recommended is True) != recommended:
            continue
        if shutting_down is not None and (m.eol_date is not None) != shutting_down:
            continue
        if max_price_usd is not None:
            norm = views.normalized_price(m)
            if norm is None or norm[0] > max_price_usd:
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
    use_case: str | None = None,
    age: str | None = None,
    has_sample: bool | None = None,
    multilingual: bool | None = None,
) -> list[VoiceRow]:
    from voicedex.web import views
    gender_val = _enum(gender, VALID_GENDERS, "gender")
    use_val = _enum_ci(use_case, list(views.VOICE_USES), "use_case")
    age_val = _enum_ci(age, list(views.VOICE_AGES), "age")
    category_val = _enum(category, VALID_CATEGORIES, "category")
    caps = set(parse_capabilities(capabilities, VOICE_CAPABILITIES, "voice"))
    incl_dep = effective_include_deprecated(include_deprecated, updated_since)
    since = _since(updated_since)
    norm_accent = lambda a: (a or "").replace("_", " ").replace("-", " ").strip().lower()   # noqa: E731
    accent_val = norm_accent(accent) if accent else None
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
        if accent_val and norm_accent(v.accent) != accent_val:
            continue
        if use_val and use_val not in views._uses(v):
            continue
        if age_val and views._age_bucket(v.age) != age_val:
            continue
        if has_sample is not None and bool(v.preview_url or v.previews) != has_sample:
            continue
        if multilingual is not None and ("*" in v.languages or len(v.languages) > 1
                                         or "multilingual_native" in v.capabilities) != multilingual:
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


MODEL_SORTS = ("name", "price", "newest")


def sort_models(rows: list[ModelRow], cross_provider: bool, sort: str | None = None) -> list[ModelRow]:
    """name (default): provider, then name. price: cheapest normalized USD first, other currencies/units after,
    unpriced last. newest: latest release first (first_seen when no release date is published)."""
    from voicedex.web import views
    sort_val = _enum(sort, set(MODEL_SORTS), "sort")
    if sort_val == "price":
        return sorted(rows, key=views.price_sort_key)
    if sort_val == "newest":
        return sorted(rows, key=views.newest_model_order)
    key = (lambda r: (r.provider_id, r.model.name.lower(), r.model.id)) if cross_provider \
        else (lambda r: (r.model.name.lower(), r.model.id))
    return sorted(rows, key=key)


def sort_voices(rows: list[VoiceRow], cross_provider: bool) -> list[VoiceRow]:
    key = (lambda r: (r.provider_id, r.voice.name.lower(), r.voice.id)) if cross_provider \
        else (lambda r: (r.voice.name.lower(), r.voice.id))
    return sorted(rows, key=key)
