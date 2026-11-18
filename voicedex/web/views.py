"""Presentation helpers for the HTML catalog pages (pure functions over the in-memory Catalog)."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass

from voicedex.catalog.schema import Model, Pricing
from voicedex.catalog.store import Catalog, ModelRow, VoiceRow
from voicedex.sync.language import LANGUAGE_NAMES

TYPE_LABELS = {"stt": "Speech-to-text", "tts": "Text-to-speech", "sts": "Speech-to-speech"}
TYPE_SHORT = {"stt": "STT", "tts": "TTS", "sts": "S2S"}

ACCESS_LABELS = {
    "self_serve": "self-serve API",
    "enterprise": "API via sales",
    "regional": "local registration required",
    "open_weights": "open weights only",
}

# Countries providers are headquartered in (ISO 3166-1 alpha-2). Unknown codes render as the code.
COUNTRY_NAMES = {
    "AE": "UAE", "AU": "Australia", "BD": "Bangladesh", "BE": "Belgium", "BR": "Brazil", "CA": "Canada",
    "CH": "Switzerland", "CN": "China", "CZ": "Czechia", "DE": "Germany", "EG": "Egypt", "ES": "Spain",
    "FR": "France", "GB": "United Kingdom", "GH": "Ghana", "HK": "Hong Kong", "ID": "Indonesia",
    "IL": "Israel", "IN": "India", "IT": "Italy", "JO": "Jordan", "JP": "Japan", "KE": "Kenya",
    "KR": "South Korea", "KZ": "Kazakhstan", "LV": "Latvia", "NG": "Nigeria", "NL": "Netherlands",
    "PK": "Pakistan", "PL": "Poland", "RO": "Romania", "RU": "Russia", "SA": "Saudi Arabia",
    "SE": "Sweden", "SG": "Singapore", "TH": "Thailand", "TR": "Turkey", "TW": "Taiwan", "UG": "Uganda",
    "US": "United States", "UZ": "Uzbekistan", "VN": "Vietnam", "ZA": "South Africa",
}


def country_name(code: str | None) -> str | None:
    return COUNTRY_NAMES.get(code, code) if code else None

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


_SYMBOL = {"USD": "$", "EUR": "€", "INR": "₹", "GBP": "£", "JPY": "¥", "CNY": "¥"}


def normalized_price(model: Model) -> tuple[float, str] | None:
    """USD only — non-USD prices are shown as published but never converted or sorted against USD."""
    p: Pricing | None = model.pricing
    if not p or p.price_usd is None:
        return None
    unit = p.unit.lower()
    if model.type == "tts" and unit == "character":
        return p.price_usd * 1_000_000, "per 1M chars"
    if model.type in ("stt", "sts") and unit in _PER_HOUR:
        return p.price_usd * _PER_HOUR[unit], "per hour"
    return None


def price_label(model: Model) -> str | None:
    p = model.pricing
    if p and (p.price_usd if p.price_usd is not None else p.price) == 0:
        return "Free"
    n = normalized_price(model)
    if n:
        value, unit = n
        return f"${value:,.2f} {unit}" if value >= 0.01 else f"${value:.4f} {unit}"
    p = model.pricing
    if p:
        amount = p.price_usd if p.price_usd is not None else p.price
        sym = _SYMBOL.get(p.currency, p.currency + " ")
        if p.unit in ("character", "byte", "token"):
            plural = {"character": "chars", "byte": "bytes", "token": "tokens"}[p.unit]
            return f"{sym}{amount * 1_000_000:,.2f} per 1M {plural}"
        return f"{sym}{amount:g} per {p.unit}"
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
    totals: dict[str, int] = None        # provider id → distinct languages overall (not just the columns shown)


def coverage_map(catalog: Catalog, n_languages: int = 48, model_type: str = "") -> CoverageMap:
    counts: dict[str, Counter] = defaultdict(Counter)
    for r in active_models(catalog):
        if model_type and r.model.type != model_type:
            continue
        for base in {base_language(lang) for lang in r.model.languages if lang != "*"}:
            counts[r.provider_id][base] += 1
    breadth = Counter(lang for c in counts.values() for lang in c)
    langs = [lang for lang, _ in breadth.most_common(n_languages)]
    summaries = [s for s in provider_summaries(catalog) if s.status == "active" and s.models]
    rows = [(s, [counts[s.id][lang] for lang in langs]) for s in summaries]
    rows.sort(key=lambda r: (-sum(1 for x in r[1] if x), r[0].name.lower()))
    return CoverageMap(langs, rows, max((x for _, cs in rows for x in cs), default=1),
                       {pid: len(c) for pid, c in counts.items()})


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


# ── Model keys, lookup, voices per model ─────────────────────────────────────

def model_key(row: ModelRow) -> str:
    """Stable URL key: provider/type/model_id (model ids may contain ':' or '/')."""
    return f"{row.provider_id}/{row.model.type}/{row.model.id}"


def model_url(row: ModelRow) -> str:
    return f"/models/{model_key(row)}"


def find_model(catalog: Catalog, key: str) -> ModelRow | None:
    parts = key.split("/", 2)
    if len(parts) != 3:
        return None
    pid, mtype, mid = parts
    return next((r for r in catalog.models if r.provider_id == pid and r.model.type == mtype
                 and r.model.id == mid), None)


def voices_for_model(catalog: Catalog, row: ModelRow) -> list[VoiceRow]:
    if row.model.type == "stt":
        return []
    return [v for v in active_voices(catalog, row.provider_id)
            if "*" in v.voice.compatible_models or row.model.id in v.voice.compatible_models]


# ── Comparison table ─────────────────────────────────────────────────────────

FEATURE_LABELS = {
    "word_timestamps": "Word timestamps", "speaker_diarization": "Speaker diarization",
    "punctuation": "Punctuation", "profanity_filter": "Profanity filter",
    "custom_vocabulary": "Custom vocabulary", "language_detection": "Language detection",
    "translation": "Translation", "sentiment": "Sentiment", "pii_redaction": "PII redaction",
    "summarization": "Summarization", "topic_detection": "Topic detection",
    "emotion": "Emotion control", "voice_cloning": "Voice cloning", "voice_design": "Voice design",
    "ssml": "SSML", "phoneme_input": "Phoneme input", "prosody_control": "Speed / prosody control",
    "style_control": "Style control", "multi_speaker": "Multi-speaker",
}
INTERFACE_LABELS = {"http": "HTTP", "websocket": "WebSocket", "grpc": "gRPC", "webrtc": "WebRTC"}


@dataclass
class CompareRow:
    label: str
    cells: list            # str, or list[str] rendered one per line
    group: str
    same: bool = False
    best: int | None = None      # index of the highlighted cell
    diff: list = None            # per cell: True when it differs from a value the others share


def _v(x) -> str:
    """Enum or plain string → its value (records may hold either)."""
    return str(getattr(x, "value", x))


def _fmt_list(items: list, empty: str = "–") -> str:
    return ", ".join(str(i) for i in items) if items else empty


def compare_table(rows: list[ModelRow], names: dict[str, str], check_language: str = "") -> list[CompareRow]:
    out: list[CompareRow] = []

    def add(group: str, label: str, cells: list[str], best: int | None = None) -> None:
        flat = [tuple(c) if isinstance(c, list) else c for c in cells]
        common = Counter(flat).most_common(1)[0][0] if flat else None
        majority = Counter(flat).most_common(1)[0][1] > 1 if flat else False
        diff = [majority and c != common for c in flat]        # outliers only; an all-different row marks nothing
        out.append(CompareRow(label, cells, group, same=len(set(flat)) <= 1 and len(cells) > 1, best=best, diff=diff))

    ms = [r.model for r in rows]
    add("Overview", "Type", [TYPE_LABELS[m.type] for m in ms])
    add("Overview", "Status", [
        (f"Shuts down {m.eol_date:%b %-d, %Y}" if m.eol_date else
         _v(m.lifecycle).capitalize() if _v(m.lifecycle) in ("alpha", "beta") else "Generally available")
        + (", provider default" if m.is_default else "") for m in ms])

    prices = [normalized_price(m) for m in ms]
    comparable = [(p[0], i) for i, p in enumerate(prices) if p]
    units = {p[1] for p in prices if p}
    best = min(comparable)[1] if len(comparable) > 1 and len(units) == 1 else None
    add("Price", "Price", [price_label(m) or "Not published" for m in ms], best=best)
    add("Price", "Other plans and modes", [
        [f"{v.applies_to}: {_variant_label(m, v)}" for v in m.pricing.variants] if m.pricing and m.pricing.variants
        else "–" for m in ms])
    add("Price", "Free tier", [
        (f"{m.pricing.free_quota.amount:,g} {m.pricing.free_quota.unit}s"
         + (f" per {m.pricing.free_quota.period}" if m.pricing.free_quota.period not in (None, "once") else ""))
        if m.pricing and m.pricing.free_quota else "–" for m in ms])

    add("Languages", "Languages", [
        "Many (unlisted)" if "*" in m.languages else (str(lang_count(m)) if m.languages else "Not published")
        for m in ms])
    if check_language:
        from voicedex.catalog.store import language_matches
        add("Languages", f"Supports {language_name(check_language)}",
            ["Not published" if not m.languages else "Yes" if language_matches(check_language, m.languages) else "No"
             for m in ms])

    caps = sorted({c for m in ms for c in m.capabilities}, key=lambda c: FEATURE_LABELS.get(c, c))
    for c in caps:
        add("Features", FEATURE_LABELS.get(c, c.replace("_", " ").capitalize()),
            ["Yes" if c in m.capabilities else "–" for m in ms])

    add("Technical", "Streaming", ["Yes" if m.streaming else "No" for m in ms])
    add("Technical", "Batch / file", ["Yes" if m.batch else "–" if m.batch is None else "No" for m in ms])
    add("Technical", "Connect via", [_fmt_list([INTERFACE_LABELS.get(i, i) for i in m.interfaces]) for m in ms])
    add("Technical", "Sample rates", [_fmt_list([f"{r / 1000:g} kHz" for r in m.sample_rates_hz]) for m in ms])
    add("Technical", "Audio formats", [_fmt_list(m.audio_formats) for m in ms])
    if any(m.max_text_chars for m in ms):
        add("Technical", "Max text per request", [f"{m.max_text_chars:,} chars" if m.max_text_chars else "–" for m in ms])
    if any(m.max_audio_seconds for m in ms):
        add("Technical", "Max audio per request",
            [_duration(m.max_audio_seconds) if m.max_audio_seconds else "–" for m in ms])
    if any(m.regions for m in ms):
        add("Technical", "Regions", [_fmt_list([_v(x).upper() if len(_v(x)) == 2 else _v(x).capitalize()
                                                for x in m.regions]) for m in ms])
    if any(m.open_weights for m in ms):
        add("Technical", "Open weights", [m.open_weights.license if m.open_weights else "No" for m in ms])
    add("Data", "Source", [
        {"api": "Provider API", "docs": "Documentation", "manual": "Manual"}.get(
            _v(m.provenance.method) if m.provenance else "", "–") for m in ms])
    add("Data", "Checked", [f"{m.provenance.as_of:%b %-d, %Y}" if m.provenance else "–" for m in ms])
    return out


def _variant_label(model: Model, v) -> str:
    amount = v.price_usd if v.price_usd is not None else v.price
    if amount == 0:
        return "Free"
    cur = model.pricing.currency if model.pricing else "USD"
    sym = _SYMBOL.get(cur, cur + " ")
    if v.unit in ("character", "byte", "token"):
        plural = {"character": "chars", "byte": "bytes", "token": "tokens"}[v.unit]
        return f"{sym}{amount * 1_000_000:,.2f} per 1M {plural}"
    if model.type in ("stt", "sts") and v.unit in _PER_HOUR and cur == "USD":
        return f"{sym}{amount * _PER_HOUR[v.unit]:,.2f} per hour"
    return f"{sym}{amount:g} per {v.unit}"


def variant_label(model: Model, v) -> str:
    return _variant_label(model, v)


def _duration(seconds: int) -> str:
    if seconds >= 3600:
        return f"{seconds / 3600:g} h"
    if seconds >= 60:
        return f"{seconds / 60:g} min"
    return f"{seconds} s"


def duration(seconds: int) -> str:
    return _duration(seconds)


def language_groups(languages: list[str]) -> list[tuple[str, list[str]]]:
    """[(language name, [regional variants…])] sorted by name; '*' handled by callers."""
    groups: dict[str, list[str]] = defaultdict(list)
    for code in languages:
        if code == "*":
            continue
        base = base_language(code)
        if code != base:
            groups[base].append(code)
        else:
            groups.setdefault(base, [])
    return sorted(((language_name(b), sorted(v)) for b, v in groups.items()), key=lambda x: x[0])


def lang_count(model: Model) -> int:
    """Distinct base languages (en-US + en-GB count once)."""
    return len({base_language(x) for x in model.languages if x != "*"})


def voice_chips(voice, limit: int = 4) -> list[str]:
    """Readable use-case/style chips: drop 'category:' prefixes and facts already shown (age, gender)."""
    out: list[str] = []
    for raw in list(voice.use_cases) + list(voice.tags):
        cat, _, val = raw.partition(":") if ":" in raw else ("", "", raw)
        if cat.lower() in ("age", "gender", "accent", "language"):
            continue
        label = val.replace("_", " ").replace("-", " ").strip()
        if label and label.lower() not in (x.lower() for x in out):
            out.append(label)
        if len(out) >= limit:
            break
    return out


# ── Price spectrum: every USD-priced model as one square in its log-price column ──

SPECTRUM_BANDS = [
    ("audio", ("stt", "sts"), "Speech-to-text and realtime", "per hour of audio"),
    ("text", ("tts",), "Text-to-speech", "per 1M characters"),
]
_NICE = [m * 10 ** e for e in range(-3, 4) for m in (1, 2, 5)]


@dataclass
class SpectrumItem:
    key: str
    url: str
    label: str
    provider: str
    price: str
    value: float
    ending: bool
    state: str = ""            # "" | "on" (highlighted) | "off" (dimmed)


@dataclass
class SpectrumBand:
    id: str
    title: str
    unit: str
    columns: list[list[SpectrumItem]]
    ticks: list[tuple[float, str]]      # (position 0–100 %, label)
    free: list[SpectrumItem]
    priced: int
    unpriced: int
    tallest: int


def _money(v: float) -> str:
    if v >= 1:
        return f"${v:,.0f}" if v == int(v) else f"${v:,.2f}"
    return f"${v:.2f}" if v >= 0.01 else f"${v:g}"


def price_spectrum(catalog: Catalog, highlight: set[str] | None = None, n_columns: int = 44) -> list[SpectrumBand]:
    """Live providers' active models. `highlight`: keys to light up; with it, every other square is dimmed."""
    live = {pid for pid, pd in catalog.providers.items() if pd.provider.status == "active"}
    names = {pid: pd.provider.name for pid, pd in catalog.providers.items()}
    bands = []
    for band_id, types, title, unit in SPECTRUM_BANDS:
        rows = [r for r in active_models(catalog) if r.provider_id in live and r.model.type in types]
        items, free, unpriced = [], [], 0
        for r in rows:
            p = r.model.pricing
            is_free = bool(p and (p.price_usd if p.price_usd is not None else p.price) == 0)
            n = normalized_price(r.model)
            if not n and not is_free:
                unpriced += 1
                continue
            key = model_key(r)
            state = "" if highlight is None else ("on" if key in highlight else "off")
            item = SpectrumItem(key, model_url(r), r.model.name, names[r.provider_id], price_label(r.model) or "",
                                0.0 if is_free else n[0], bool(r.model.eol_date), state)
            (free if is_free else items).append(item)
        if not items:
            continue
        lo, hi = math.log10(min(i.value for i in items)), math.log10(max(i.value for i in items))
        span = (hi - lo) or 1.0
        columns: list[list[SpectrumItem]] = [[] for _ in range(n_columns)]
        for it in sorted(items, key=lambda i: i.value):
            idx = min(n_columns - 1, int((math.log10(it.value) - lo) / span * n_columns))
            columns[idx].append(it)
        for col in columns:                      # highlighted squares first, so a capped stack still shows them
            col.sort(key=lambda i: i.state != "on")
        nice = [v for v in _NICE if lo <= math.log10(v) <= hi]
        step = max(1, math.ceil(len(nice) / 6))
        ticks = [((math.log10(v) - lo) / span * 100, _money(v)) for v in nice[::step]]
        bands.append(SpectrumBand(band_id, title, unit, columns, ticks, free, len(items) + len(free), unpriced,
                                  max(len(c) for c in columns)))
    return bands


def price_rank(catalog: Catalog, row: ModelRow) -> tuple[int, int] | None:
    """(share of priced peers in the same band that cost more, peer count) — for "cheaper than N%"."""
    n = normalized_price(row.model)
    if not n:
        return None
    band = next(t for _, t, _, _ in SPECTRUM_BANDS if row.model.type in t)
    live = {pid for pid, pd in catalog.providers.items() if pd.provider.status == "active"}
    peers = [normalized_price(r.model) for r in active_models(catalog) if r.model.type in band and r.provider_id in live]
    peers = [p[0] for p in peers if p]
    if len(peers) < 5:
        return None
    pricier = sum(1 for v in peers if v > n[0])
    return round(100 * pricier / len(peers)), len(peers)


@dataclass
class Timeline:
    months: list[tuple[float, str]]          # (position %, "Jan") — year shown on January and at the start
    items: list[tuple[float, ModelRow]]      # (position %, row)
    span_days: int


def shutdown_timeline(rows: list[ModelRow], today, months_ahead: int = 12) -> Timeline | None:
    """Upcoming shutdowns on a fixed axis from today; later dates are pinned to the right edge."""
    from datetime import date
    if not rows:
        return None
    y, m = today.year, today.month
    end_y, end_m = y + (m - 1 + months_ahead) // 12, (m - 1 + months_ahead) % 12 + 1
    end = date(end_y, end_m, 1)
    span = (end - today).days
    def pos(d) -> float:
        return max(0.0, min(100.0, (d - today).days / span * 100))
    months = []
    for i in range(1, months_ahead + 1):
        yy, mm = y + (m - 1 + i) // 12, (m - 1 + i) % 12 + 1
        d = date(yy, mm, 1)
        months.append((pos(d), d.strftime("%b") + (f" {yy}" if mm == 1 or i == 1 else "")))
    return Timeline(months, [(pos(r.model.eol_date), r) for r in rows if r.model.eol_date], span)


def price_positions(bands: list[SpectrumBand]) -> dict[str, float]:
    """Model key → 0–100 position of its price within its spectrum band (log scale), for table micro-bars."""
    out = {}
    for b in bands:
        vals = [it.value for col in b.columns for it in col]
        if not vals:
            continue
        lo, hi = math.log10(min(vals)), math.log10(max(vals))
        for col in b.columns:
            for it in col:
                out[it.key] = 6 + 94 * ((math.log10(it.value) - lo) / ((hi - lo) or 1))
        for it in b.free:
            out[it.key] = 2
    return out


def feature_vocab(model_type: str) -> list[str]:
    """The controlled feature vocabulary that applies to a model type (for checklists and n/total counts)."""
    from voicedex.catalog.schema import MODEL_CAPABILITIES, STT_CAPABILITIES, TTS_CAPABILITIES
    vocab = {"stt": STT_CAPABILITIES, "tts": TTS_CAPABILITIES}.get(str(model_type), MODEL_CAPABILITIES)
    order = list(FEATURE_LABELS)
    return sorted(vocab, key=lambda c: order.index(c) if c in order else len(order))
