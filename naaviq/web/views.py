"""Presentation helpers for the HTML catalog pages (pure functions over the in-memory Catalog)."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from naaviq.catalog.schema import Model, Pricing
from naaviq.catalog.store import Catalog, ModelRow, VoiceRow
from naaviq.sync.language import LANGUAGE_NAMES

TYPE_LABELS = {"stt": "Speech-to-text", "tts": "Text-to-speech", "sts": "Speech-to-speech"}
TYPE_SHORT = {"stt": "STT", "tts": "TTS", "sts": "S2S"}

_CODE_TO_NAME: dict[str, str] = {}
for _name, _code in LANGUAGE_NAMES.items():
    _CODE_TO_NAME.setdefault(_code, _name.title())
_CODE_TO_NAME.update({"zh": "Chinese", "es-419": "Spanish (Latin America)", "yue": "Cantonese"})


def language_name(code: str) -> str:
    if code == "*":
        return "Many languages"
    base, _, region = code.partition("-")
    name = _CODE_TO_NAME.get(code) or _CODE_TO_NAME.get(base) or code
    return f"{name} ({region})" if region and code not in _CODE_TO_NAME else name


def base_language(code: str) -> str:
    return code.split("-")[0].lower()


# ── Pricing, normalized for comparison ───────────────────────────────────────
# TTS → USD per 1M characters; STT/STS → USD per hour of audio. None when not comparable.

_PER_HOUR = {"hour": 1, "minute": 60, "second": 3600}


def normalized_price(model: Model) -> tuple[float, str] | None:
    p: Pricing | None = model.pricing
    if not p:
        return None
    unit = p.unit.lower()
    if model.type == "tts" and unit == "character":
        return p.price_usd * 1_000_000, "per 1M chars"
    if model.type in ("stt", "sts") and unit in _PER_HOUR:
        return p.price_usd * _PER_HOUR[unit], "per hour"
    return None


def price_label(model: Model) -> str | None:
    n = normalized_price(model)
    if n:
        value, unit = n
        return f"${value:,.2f} {unit}" if value >= 0.01 else f"${value:.4f} {unit}"
    if model.pricing:
        return f"${model.pricing.price_usd:g} per {model.pricing.unit}"
    return None


# ── Provider summaries ───────────────────────────────────────────────────────

@dataclass
class ProviderSummary:
    id: str
    name: str
    status: str
    types: list[str]
    models: int
    voices: int
    languages: int
    multilingual: bool
    last_synced: str | None
    description: str | None
    retired_on: str | None
    website: str | None


def active_models(catalog: Catalog, provider_id: str | None = None) -> list[ModelRow]:
    return [r for r in catalog.models if r.model.deprecated_at is None
            and (provider_id is None or r.provider_id == provider_id)]


def active_voices(catalog: Catalog, provider_id: str | None = None) -> list[VoiceRow]:
    return [r for r in catalog.voices if r.voice.deprecated_at is None
            and (provider_id is None or r.provider_id == provider_id)]


def provider_summaries(catalog: Catalog) -> list[ProviderSummary]:
    models_by = defaultdict(list)
    for r in active_models(catalog):
        models_by[r.provider_id].append(r.model)
    voices_by = Counter(r.provider_id for r in active_voices(catalog))
    out = []
    for pid, pd in catalog.providers.items():
        p = pd.provider
        ms = models_by.get(pid, [])
        langs = {base_language(lang) for m in ms for lang in m.languages if lang != "*"}
        out.append(ProviderSummary(
            id=pid, name=p.name, status=p.status,
            types=[t for t in ("stt", "tts", "sts") if any(m.type == t for m in ms)],
            models=len(ms), voices=voices_by.get(pid, 0), languages=len(langs),
            multilingual=any("*" in m.languages for m in ms),
            last_synced=p.last_synced.isoformat() if p.last_synced else None,
            description=p.description, retired_on=p.retired_on.isoformat() if p.retired_on else None,
            website=p.website,
        ))
    return sorted(out, key=lambda s: s.name.lower())


# ── Coverage map: providers × languages ──────────────────────────────────────

@dataclass
class CoverageMap:
    languages: list[str]                 # base codes, most-covered first
    rows: list[tuple[ProviderSummary, list[int]]]  # model count per language
    max_count: int


def coverage_map(catalog: Catalog, n_languages: int = 32) -> CoverageMap:
    counts: dict[str, Counter] = defaultdict(Counter)
    for r in active_models(catalog):
        for base in {base_language(lang) for lang in r.model.languages if lang != "*"}:
            counts[r.provider_id][base] += 1
    breadth = Counter(lang for c in counts.values() for lang in c)
    langs = [lang for lang, _ in breadth.most_common(n_languages)]
    summaries = [s for s in provider_summaries(catalog) if s.status == "active" and s.models]
    rows = [(s, [counts[s.id][lang] for lang in langs]) for s in summaries]
    rows.sort(key=lambda r: (-sum(1 for x in r[1] if x), r[0].name.lower()))
    return CoverageMap(langs, rows, max((x for _, cs in rows for x in cs), default=1))


def heat_level(count: int, max_count: int) -> int:
    """0 = none, 1–5 = ramp step (log-ish so one-model coverage is still visible)."""
    if count <= 0:
        return 0
    if max_count <= 1:
        return 5
    for level, bound in enumerate((1, 2, 4, 8), start=1):
        if count <= bound:
            return level
    return 5


# ── Filtering for the HTML lists (mirrors the API semantics) ──────────────────

def language_options(catalog: Catalog) -> list[tuple[str, str]]:
    seen = Counter(base_language(lang) for r in active_models(catalog) for lang in r.model.languages if lang != "*")
    return sorted(((code, language_name(code)) for code in seen), key=lambda x: x[1])
