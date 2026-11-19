"""Presentation helpers for the HTML catalog pages (pure functions over the in-memory Catalog)."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date

from voicedex.catalog.schema import Model, Pricing
from voicedex.catalog.store import Catalog, ModelRow, VoiceRow, language_matches
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
    headquarters: str | None = None
    access: str | None = None


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
            headquarters=p.headquarters, access=p.access,
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


def coverage_map(catalog: Catalog, n_languages: int = 48, model_type: str = "",
                 n_providers: int | None = None) -> CoverageMap:
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
    if n_providers is not None:
        rows = rows[:n_providers]
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


# ── Voice samples: play the one in the language the visitor filtered for ─────

@dataclass(frozen=True)
class Sample:
    url: str
    language: str | None   # language spoken in the sample; None = the provider doesn't say
    matched: bool | None   # True/False vs the language filter; None when no filter is set


def sample_language(voice) -> str | None:
    """The stated sample language, or the voice's only language (a monolingual voice's sample is in it)."""
    if voice.preview_language:
        return voice.preview_language
    langs = voice.languages
    if langs and "*" not in langs and len({base_language(code) for code in langs}) == 1:
        return langs[0]
    return None


def voice_sample(voice, language: str | None = None) -> Sample | None:
    candidates = [(p.url, p.language) for p in voice.previews]
    if voice.preview_url:
        candidates.insert(0, (voice.preview_url, sample_language(voice)))
    if not candidates:
        return None
    if not language:
        url, lang = candidates[0]
        return Sample(url, lang, None)
    for url, lang in candidates:
        if lang and language_matches(language, [lang]):
            return Sample(url, lang, True)
    url, lang = candidates[0]
    return Sample(url, lang, False)



# ── Landing pages: one indexable URL per question people search for ──────────
# "/text-to-speech", "/text-to-speech/hindi", "/speech-to-text/speaker-diarization", "/text-to-speech/open-source".
# Filtered /models?… views canonicalize to /models, so without these no filter combination is indexable.
# Generated from data (never a hand-kept list); a page exists only when it has MIN_LANDING_MODELS to compare.

TYPE_SLUGS = {"stt": "speech-to-text", "tts": "text-to-speech", "sts": "speech-to-speech"}
SLUG_TYPES = {v: k for k, v in TYPE_SLUGS.items()}
MIN_LANDING_MODELS = 3
OPEN_WEIGHTS_SLUG = "open-source"


def slugify(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@dataclass(frozen=True)
class Landing:
    type: str            # stt | tts | sts
    kind: str            # hub | language | feature | open
    value: str = ""      # base language code, or capability
    slug: str = ""
    label: str = ""      # "Hindi", "Speaker diarization"

    @property
    def url(self) -> str:
        return f"/{TYPE_SLUGS[self.type]}" + (f"/{self.slug}" if self.slug else "")

    def matches(self, row: ModelRow) -> bool:
        m = row.model
        if m.type != self.type:
            return False
        if self.kind == "language":       # explicit support only: "*" models don't claim this language
            return any(base_language(lang) == self.value for lang in m.languages if lang != "*")
        if self.kind == "feature":
            return self.value in m.capabilities
        if self.kind == "open":
            return m.open_weights is not None
        return True


_LANDING_CACHE: list = [None, {}]


def landing_pages(catalog: Catalog) -> dict[str, Landing]:
    """Every landing page, keyed by URL path. Memoized per loaded catalog (the catalog is immutable)."""
    if _LANDING_CACHE[0] is catalog and _LANDING_CACHE[2:] == [MIN_LANDING_MODELS]:
        return _LANDING_CACHE[1]
    rows = active_models(catalog)
    out: dict[str, Landing] = {}
    for mtype in TYPE_SLUGS:
        typed = [r for r in rows if r.model.type == mtype]
        if not typed:
            continue
        hub = Landing(mtype, "hub")
        out[hub.url] = hub
        candidates: list[Landing] = []
        if sum(r.model.open_weights is not None for r in typed) >= MIN_LANDING_MODELS:
            candidates.append(Landing(mtype, "open", slug=OPEN_WEIGHTS_SLUG, label="Open-weights"))
        caps = Counter(c for r in typed for c in r.model.capabilities)
        for cap in sorted(c for c, n in caps.items() if n >= MIN_LANDING_MODELS):
            candidates.append(Landing(mtype, "feature", cap, slugify(cap), FEATURE_LABELS.get(cap, cap)))
        langs = Counter(b for r in typed for b in {base_language(lang) for lang in r.model.languages if lang != "*"})
        names = {code: language_name(code) for code, n in langs.items() if n >= MIN_LANDING_MODELS}
        name_slugs = Counter(slugify(n) for n in names.values())
        for code, name in sorted(names.items(), key=lambda x: x[1]):
            slug = slugify(name) if name != code and name_slugs[slugify(name)] == 1 and slugify(name) else slugify(code)
            candidates.append(Landing(mtype, "language", code, slug, name))
        for page in candidates:
            out.setdefault(page.url, page)        # first wins on a (theoretical) slug collision
    _LANDING_CACHE[:] = [catalog, out, MIN_LANDING_MODELS]
    return out


def find_landing(catalog: Catalog, mtype: str, kind: str = "hub", value: str = "") -> Landing | None:
    return next((p for p in landing_pages(catalog).values()
                 if p.type == mtype and p.kind == kind and p.value == value), None)


def landing_rows(catalog: Catalog, page: Landing) -> list[ModelRow]:
    """Cheapest first (USD-normalized), then unpriced; stable within ties."""
    rows = [r for r in active_models(catalog) if page.matches(r)]
    return sorted(rows, key=lambda r: ((normalized_price(r.model) or (math.inf,))[0], r.provider_id, r.model.id))


def _lower_label(label: str) -> str:
    return label if label[:2].isupper() else label[0].lower() + label[1:]


@dataclass
class LandingCopy:
    title: str
    h1: str
    description: str
    intro: list[str]


def landing_copy(catalog: Catalog, page: Landing, rows: list[ModelRow]) -> LandingCopy:
    """Titles and an intro written from the data, so every page says something specific and true."""
    kind_label = TYPE_LABELS[page.type].lower()                       # "text-to-speech"
    abbr = f" ({TYPE_SHORT[page.type]})"                               # people search "TTS API" too
    n, n_prov = len(rows), len({r.provider_id for r in rows})
    noun = f"model{'s' if n != 1 else ''}"
    if page.kind == "language":
        subject = f"{page.label} {kind_label}"
        h1 = f"{page.label} {kind_label} models"
        title = f"{page.label} {kind_label}{abbr} APIs: {n} models compared by price"
        lead = f"{n} {kind_label} {noun} from {n_prov} provider{'s' if n_prov != 1 else ''} list {page.label} support."
    elif page.kind == "feature":
        feat = _lower_label(page.label)
        subject = f"{kind_label} with {feat}"
        h1 = f"{TYPE_LABELS[page.type]} models with {feat}"
        title = f"{TYPE_LABELS[page.type]}{abbr} APIs with {feat}: {n} models compared"
        lead = f"{n} {kind_label} {noun} from {n_prov} provider{'s' if n_prov != 1 else ''} list {feat} as a feature."
    elif page.kind == "open":
        subject = f"open-weights {kind_label}"
        h1 = f"Open-source {kind_label} models"
        title = f"Open-source {kind_label}{abbr} models: {n} open-weights models compared"
        lead = (f"{n} {kind_label} {noun} from {n_prov} publisher{'s' if n_prov != 1 else ''} publish their weights, "
                "so you can run them yourself. Licences differ, so check commercial use on each model.")
    else:
        subject = kind_label
        h1 = f"{TYPE_LABELS[page.type]}{abbr} APIs and models compared"
        title = f"{TYPE_LABELS[page.type]}{abbr} APIs compared: {n} models, prices and languages"
        lead = f"{n} {kind_label} {noun} from {n_prov} providers, with languages, features, prices and shutdown dates."
    intro = [lead]
    priced = [(normalized_price(r.model), r) for r in rows if normalized_price(r.model)]
    paid = [x for x in priced if x[0][0] > 0]
    if paid:
        _, cheapest = min(paid, key=lambda x: x[0][0])
        name = catalog.providers[cheapest.provider_id].provider.name
        intro.append(f"The cheapest published USD price is {cheapest.model.name} from {name} at "
                     f"{price_label(cheapest.model)}; {len(priced)} of {n} have a comparable price.")
    extras = []
    if n_free := len(priced) - len(paid):
        extras.append(f"{n_free} {'are' if n_free != 1 else 'is'} free")
    if page.kind != "open" and (n_open := sum(r.model.open_weights is not None for r in rows)):
        extras.append(f"{n_open} {'are' if n_open != 1 else 'is'} open weights")
    if n_rt := sum(any(str(i) in ("websocket", "webrtc") for i in r.model.interfaces) for r in rows):
        extras.append(f"{n_rt} stream over WebSocket or WebRTC")
    if n_eol := sum(r.model.eol_date is not None for r in rows):
        extras.append(f"{n_eol} {'have' if n_eol != 1 else 'has'} an announced shutdown date")
    if extras:
        intro.append(("Of these, " + ", ".join(extras[:-1]) + (" and " if len(extras) > 1 else "") + extras[-1] + "."))
    description = f"Compare {n} {subject}{abbr} {noun}: prices, languages, features and status."
    if paid:
        description += f" Cheapest paid: {cheapest.model.name} ({name}), {price_label(cheapest.model)}."
    return LandingCopy(title=title, h1=h1, description=description, intro=intro)


def last_modified(rows) -> date | None:
    """Most recent change among model or voice rows (for sitemap <lastmod> and Dataset dateModified)."""
    dates = [d for r in rows for rec in [getattr(r, "model", None) or r.voice] for d in (rec.updated_at, rec.first_seen) if d]
    return max(dates) if dates else None


# ── Provider vs provider pages (/compare/<a>-vs-<b>) ─────────────────────────
# Editorial, not catalog data: the providers people actually weigh against each other when choosing a vendor.
# Pages are generated only for pairs that both still sell at least one model of a shared type, so retired or
# irrelevant pairs never appear. Order here doesn't matter (URLs are alphabetical).
COMPARE_PROVIDERS = (
    "elevenlabs", "cartesia", "deepgram", "assemblyai", "openai", "google-cloud", "azure", "amazon-polly",
    "amazon-transcribe", "speechmatics", "revai", "gladia", "soniox", "rime", "inworld", "murf", "speechify",
    "fishaudio", "sarvam", "wellsaid", "groq", "minimax",
)


def provider_pair_slug(a: str, b: str) -> str:
    x, y = sorted((a, b))
    return f"{x}-vs-{y}"


def _live_types(catalog: Catalog, pid: str) -> set[str]:
    return {r.model.type for r in active_models(catalog, pid)}


def provider_pairs(catalog: Catalog) -> list[tuple[str, str]]:
    """Every (a, b) with a < b, both active, sharing at least one model type."""
    ids = sorted(p for p in COMPARE_PROVIDERS if p in catalog.providers
                 and catalog.providers[p].provider.status == "active" and _live_types(catalog, p))
    types = {p: _live_types(catalog, p) for p in ids}
    return [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:] if types[a] & types[b]]


def compare_partners(catalog: Catalog, pid: str) -> list[str]:
    return [b if a == pid else a for a, b in provider_pairs(catalog) if pid in (a, b)]


@dataclass
class TypeSide:
    """One provider's offer for one model type."""
    models: list[ModelRow]
    cheapest: ModelRow | None
    price_range: tuple[str, str] | None     # labels of the cheapest and dearest comparable USD price
    priced: int
    languages: int                          # distinct base languages listed (0 = only "many")
    many_languages: bool
    features: set[str]
    open_weights: int
    streaming: int
    ending: int


def type_side(rows: list[ModelRow]) -> TypeSide:
    priced = sorted((r for r in rows if (normalized_price(r.model) or (0,))[0] > 0),
                    key=lambda r: normalized_price(r.model)[0])
    langs = {base_language(lang) for r in rows for lang in r.model.languages if lang != "*"}
    return TypeSide(
        models=sorted(rows, key=lambda r: (not r.model.is_default, r.model.eol_date is not None,
                                           (normalized_price(r.model) or (math.inf,))[0], r.model.id)),
        cheapest=priced[0] if priced else None,
        price_range=(price_label(priced[0].model), price_label(priced[-1].model)) if priced else None,
        priced=len(priced),
        languages=len(langs),
        many_languages=any("*" in r.model.languages for r in rows),
        features={c for r in rows for c in r.model.capabilities},
        open_weights=sum(r.model.open_weights is not None for r in rows),
        streaming=sum(bool(r.model.streaming) or any(str(i) in ("websocket", "webrtc") for i in r.model.interfaces)
                      for r in rows),
        ending=sum(r.model.eol_date is not None for r in rows),
    )


@dataclass
class ProviderComparison:
    a: str
    b: str
    types: list[str]                                   # shared types, stt/tts/sts order
    sides: dict[str, dict[str, TypeSide]]              # type -> provider id -> side
    only: dict[str, list[str]]                         # provider id -> types only it offers
    voices: dict[str, int]
    title: str
    description: str
    intro: list[str]


def provider_comparison(catalog: Catalog, a: str, b: str) -> ProviderComparison:
    pa, pb = catalog.providers[a].provider, catalog.providers[b].provider
    ta, tb = _live_types(catalog, a), _live_types(catalog, b)
    shared = [t for t in TYPE_SLUGS if t in ta and t in tb]
    sides = {t: {pid: type_side([r for r in active_models(catalog, pid) if r.model.type == t]) for pid in (a, b)}
             for t in shared}
    voices = {pid: len(active_voices(catalog, pid)) for pid in (a, b)}
    kinds = " and ".join(TYPE_LABELS[t].lower() for t in shared)
    short = "/".join(TYPE_SHORT[t] for t in shared)
    title = f"{pa.name} vs {pb.name}: {short} models, pricing and languages compared"
    intro = []
    for t in shared:
        parts = []
        for pid, p in ((a, pa), (b, pb)):
            s = sides[t][pid]
            n = len(s.models)
            bit = f"{p.name} lists {n} {TYPE_LABELS[t].lower()} model{'s' if n != 1 else ''}"
            if s.cheapest:
                bit += f" from {price_label(s.cheapest.model)}"
            parts.append(bit)
        intro.append("; ".join(parts) + ".")
    desc = (f"{pa.name} vs {pb.name} compared side by side: {kinds} models, prices, languages, features, "
            f"streaming and shutdown dates, from each provider's own docs and pricing pages.")
    return ProviderComparison(
        a=a, b=b, types=shared, sides=sides,
        only={a: [t for t in TYPE_SLUGS if t in ta and t not in tb], b: [t for t in TYPE_SLUGS if t in tb and t not in ta]},
        voices=voices, title=title, description=desc, intro=intro)


# ── "Alternatives to X" pages (/alternatives/<provider>) ─────────────────────
# Subjects: the featured providers people compare (COMPARE_PROVIDERS) plus every retired provider, since
# "<retired provider> alternative" is what people search for once a service shuts down. Alternatives: every
# active provider selling a model of the same type: widely used providers (COMPARE_PROVIDERS) first, then by how
# many of the subject's listed features they also list, then by cheapest comparable price.
ALTERNATIVES_SHOWN = 15


def _provider_types(catalog: Catalog, pid: str) -> list[str]:
    live = _live_types(catalog, pid)
    if live:
        return [t for t in TYPE_SLUGS if t in live]
    declared = str(catalog.providers[pid].provider.type or "")
    wanted = {"stt", "tts"} if declared == "both" else {declared}
    wanted |= {r.model.type for r in catalog.models if r.provider_id == pid}       # retired: whatever it sold
    return [t for t in TYPE_SLUGS if t in wanted]


def alternatives_subjects(catalog: Catalog) -> list[str]:
    featured = [p for p in COMPARE_PROVIDERS if p in catalog.providers
                and catalog.providers[p].provider.status == "active" and _live_types(catalog, p)]
    retired = [p for p, pd in catalog.providers.items() if pd.provider.status != "active" and _provider_types(catalog, p)]
    return sorted(set(featured) | set(retired))


@dataclass
class Alternative:
    provider_id: str
    name: str
    side: TypeSide
    shared_features: int
    vs_slug: str | None          # /compare/<slug> when that pair page exists


@dataclass
class AlternativesPage:
    subject: str
    retired: bool
    retired_on: str | None
    types: list[str]
    subject_sides: dict[str, TypeSide | None]          # None for a retired provider with no models left
    subject_features: dict[str, set[str]]
    alternatives: dict[str, list[Alternative]]          # type -> ranked, truncated
    totals: dict[str, int]                              # type -> all active providers selling it
    cheaper: dict[str, int]                             # type -> how many list a lower starting price
    title: str
    description: str
    intro: list[str]


def alternatives_page(catalog: Catalog, pid: str) -> AlternativesPage:
    p = catalog.providers[pid].provider
    retired = p.status != "active"
    types = _provider_types(catalog, pid)
    pairs = {frozenset(x) for x in provider_pairs(catalog)}
    sides: dict[str, TypeSide | None] = {}
    feats: dict[str, set[str]] = {}
    alts: dict[str, list[Alternative]] = {}
    totals: dict[str, int] = {}
    cheaper: dict[str, int] = {}
    for t in types:
        own_active = [r for r in active_models(catalog, pid) if r.model.type == t]
        own_any = own_active or [r for r in catalog.models if r.provider_id == pid and r.model.type == t]
        sides[t] = type_side(own_active) if own_active else None
        feats[t] = {c for r in own_any for c in r.model.capabilities}
        floor = (normalized_price(sides[t].cheapest.model)[0] if sides[t] and sides[t].cheapest else None)
        cands: list[Alternative] = []
        for other, pd in catalog.providers.items():
            if other == pid or pd.provider.status != "active":
                continue
            rows = [r for r in active_models(catalog, other) if r.model.type == t]
            if not rows:
                continue
            side = type_side(rows)
            cands.append(Alternative(other, pd.provider.name, side, len(feats[t] & side.features),
                                     provider_pair_slug(pid, other) if frozenset((pid, other)) in pairs else None))
        price = lambda a: normalized_price(a.side.cheapest.model)[0] if a.side.cheapest else math.inf  # noqa: E731
        featured = set(COMPARE_PROVIDERS)
        # widely used providers first (what people expect on these pages), then shared features, then price
        overlap = len(feats[t]) >= 3            # with only one or two listed features, overlap is noise
        cands.sort(key=lambda a: (a.provider_id not in featured, -a.shared_features if overlap else 0,
                                  price(a), a.name.lower()))
        totals[t] = len(cands)
        cheaper[t] = sum(1 for a in cands if floor is not None and price(a) < floor)
        alts[t] = cands[:ALTERNATIVES_SHOWN]
    labels = [TYPE_LABELS[t].lower() for t in types]
    kinds = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]
    n_alt = len({a.provider_id for t in types for a in alts[t]})
    shorts = [TYPE_SHORT[t] for t in types]
    short = shorts[0] if len(shorts) == 1 else ", ".join(shorts[:-1]) + " and " + shorts[-1]
    title = f"{p.name} alternatives: {short} APIs compared by price and features"
    intro: list[str] = []
    if retired:
        intro.append(f"Looking for a {p.name} replacement? These providers offer the same kinds of models today.")
    for t in types:
        s = sides[t]
        lead = (f"{p.name} lists {len(s.models)} {TYPE_LABELS[t].lower()} model{'s' if len(s.models) != 1 else ''}"
                + (f" from {price_label(s.cheapest.model)}" if s.cheapest else "") + ". ") if s else ""
        intro.append(lead + f"{totals[t]} other providers offer {TYPE_LABELS[t].lower()} models"
                     + (f"; {cheaper[t]} list a lower starting price." if s and s.cheapest else "."))
    desc = (f"The best {p.name} alternatives for {kinds}: {n_alt} providers compared by price, languages, "
            "features and streaming, from each provider's own docs and pricing pages.")
    return AlternativesPage(subject=pid, retired=retired,
                            retired_on=p.retired_on.isoformat() if p.retired_on else None, types=types,
                            subject_sides=sides, subject_features=feats, alternatives=alts, totals=totals,
                            cheaper=cheaper, title=title, description=desc, intro=intro)


REPO_URL = "https://github.com/chandradot99/voicedex"


def report_url(provider_id: str, model_id: str | None = None, page: str | None = None) -> str:
    """A pre-filled 'Data correction' GitHub issue for a provider (and optionally one model)."""
    from urllib.parse import urlencode
    title = f"Data: {provider_id}" + (f" / {model_id}" if model_id else "")
    q = {"template": "data-correction.yml", "title": title, "provider": provider_id}
    if model_id:
        q["model"] = model_id
    if page:
        q["page"] = page
    return f"{REPO_URL}/issues/new?{urlencode(q)}"


VERIFICATION_DOC = f"{REPO_URL}/blob/main/docs/verification.md"


@dataclass
class VerificationStatus:
    by: str
    on: str
    scope: list[str]
    changed_models: int   # active models updated after the provider's review
    changed_voices: int


def verification_status(catalog: Catalog, provider_id: str) -> VerificationStatus | None:
    """The provider's review of its own listing, and how much has changed since (None if never reviewed)."""
    v = catalog.providers[provider_id].provider.verified
    if v is None:
        return None
    return VerificationStatus(
        by=v.by, on=v.on.isoformat(), scope=list(v.scope),
        changed_models=sum(1 for r in active_models(catalog, provider_id) if r.model.updated_at and r.model.updated_at > v.on),
        changed_voices=sum(1 for r in active_voices(catalog, provider_id) if r.voice.updated_at and r.voice.updated_at > v.on),
    )
