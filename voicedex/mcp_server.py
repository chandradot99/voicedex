"""Remote MCP server at /mcp: lets AI assistants (Claude, Cursor, ...) query the catalog directly.

Streamable HTTP, stateless, JSON responses, read-only. It reads the same in-memory Catalog the REST API and the
site serve (set in main's lifespan), so it adds no state and scales to zero like the rest of the app.
"""

from __future__ import annotations

import difflib
import math
import re
from typing import Any, Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from voicedex.catalog.schema import MODEL_CAPABILITIES
from voicedex.catalog.store import Catalog, language_matches
from voicedex.config import settings
from voicedex.web import views
from voicedex.web.changes import KIND_LABELS, load_changes

MAX_LIMIT = 50
READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)

ModelType = Literal["stt", "tts", "sts"]

server = MCPServer(
    name="voicedex",
    title="Voicedex",
    description="Open catalog of speech AI: speech-to-text, text-to-speech and speech-to-speech models and voices "
                "from 120+ providers, with normalized prices, languages, features and shutdown dates.",
    website_url=settings.site_url,
    instructions=(
        "Use these tools to find, compare and price speech AI models (STT = speech-to-text, TTS = text-to-speech, "
        "STS = speech-to-speech/realtime) and voices. Prices are normalized: TTS in USD per 1M characters, STT and "
        "STS in USD per hour of audio; non-USD prices are shown as published and never converted. Languages are "
        "BCP-47 ('hi' matches 'hi-IN'); 'many' means the provider supports many languages without listing them. "
        "A missing capability means 'not documented', not 'unsupported'. Cite the returned url so users can verify."
    ),
)


def _cat() -> Catalog:
    """The catalog the app is serving right now (app.state.catalog, set at startup; swapped in tests)."""
    from voicedex.main import app  # lazy: main imports this module
    return app.state.catalog


def _site() -> str:
    return settings.site_url.rstrip("/")


def _limit(n: int) -> int:
    return max(1, min(int(n), MAX_LIMIT))


def _page(rows: list, limit: int, offset: int) -> tuple[list, dict[str, Any]]:
    n, off = _limit(limit), max(0, int(offset))
    chunk = rows[off:off + n]
    nxt = off + n if off + n < len(rows) else None
    return chunk, {"total": len(rows), "returned": len(chunk), "offset": off, "next_offset": nxt}


def _price_note(cat: Catalog, provider_id: str, m) -> str | None:
    """Why there's no comparable USD price, so an agent never reads 'no price' as 'free' or guesses one."""
    p = m.pricing
    if p is None:
        enterprise = str(cat.providers[provider_id].provider.access) == "enterprise"
        return "no per-unit price published (" + ("enterprise / contact sales" if enterprise
                                                 else "plan/credit-based, enterprise, or not public") + ")"
    if (p.price_usd if p.price_usd is not None else p.price) == 0:
        return "free" + (f": {p.notes[:160]}" if p.notes else "")
    if p.price_usd is None:
        return f"published in {p.currency} ({p.price} per {p.unit}); not converted to USD"
    if views.normalized_price(m) is None:
        target = "1M characters" if m.type == "tts" else "hour of audio"
        return f"priced per {p.unit}, not directly comparable per {target}"
    return None


def _model_summary(cat: Catalog, r) -> dict[str, Any]:
    m = r.model
    norm = views.normalized_price(m)
    p = m.pricing
    note = _price_note(cat, r.provider_id, m) if not norm or norm[0] == 0 else None
    return {
        "key": views.model_key(r),
        "provider": r.provider_id,
        "provider_name": cat.providers[r.provider_id].provider.name,
        "id": m.id,
        "name": m.name,
        "type": str(m.type),
        "price": views.price_label(m),
        "price_usd_normalized": round(norm[0], 6) if norm else None,
        "price_unit": norm[1] if norm else None,
        "price_note": note,
        "price_source": p.source_url if p else None,
        "price_checked": p.as_of.isoformat() if p and p.as_of else None,
        "data_checked": m.provenance.as_of.isoformat() if m.provenance else None,
        "languages": "many" if "*" in m.languages else len({views.base_language(lang) for lang in m.languages}),
        "capabilities": sorted(m.capabilities),
        "streaming": any(str(i) in ("websocket", "webrtc") for i in m.interfaces),
        "open_weights": m.open_weights is not None,
        "lifecycle": str(m.lifecycle),
        "eol_date": m.eol_date.isoformat() if m.eol_date else None,
        "url": _site() + views.model_url(r),
    }


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def resolve_model(cat: Catalog, ref: str):
    """A model from an exact key ("deepgram/stt/nova-3-general") or a loose name ("deepgram nova-3",
    "ElevenLabs Flash v2.5"). Returns (row, suggestions): row is None when nothing or several things match."""
    r = views.find_model(cat, ref.strip())
    if r:
        return r, []
    rows = views.active_models(cat)
    words = ref.strip().split()
    provs = {pid for pid, pd in cat.providers.items()
             for w in (words[:1] + [" ".join(words[:2])]) if w and (_norm(w) == _norm(pid) or _norm(w) == _norm(pd.provider.name))}
    rest = ref
    if provs:
        rows = [r for r in rows if r.provider_id in provs]
        name = next(cat.providers[pid].provider.name for pid in provs)
        for prefix in (name, *provs):
            if _norm(ref).startswith(_norm(prefix)):
                rest = ref[len(prefix):] if ref.lower().startswith(prefix.lower()) else " ".join(words[1:])
                break
    q = _norm(rest) or _norm(ref)
    exact = [r for r in rows if q in (_norm(r.model.id), _norm(r.model.name))]
    partial = exact or [r for r in rows if q and (q in _norm(r.model.id) or q in _norm(r.model.name))]
    if len(partial) == 1:
        return partial[0], []
    if partial:                                   # prefer the provider's default, then the shortest id
        partial.sort(key=lambda r: (not r.model.is_default, r.model.eol_date is not None, len(r.model.id)))
        if partial[0].model.is_default or len(exact) == 1:
            return partial[0], []
        return None, [views.model_key(r) for r in partial[:5]]
    pool = {f"{cat.providers[r.provider_id].provider.name} {r.model.name}".lower(): views.model_key(r)
            for r in views.active_models(cat)}
    close = difflib.get_close_matches(ref.lower(), list(pool), n=5, cutoff=0.4)
    return None, [pool[c] for c in close]


@server.tool(annotations=READ_ONLY)
def search_models(
    type: ModelType | None = None,
    language: str | None = None,
    capability: str | None = None,
    provider: str | None = None,
    region: Literal["us", "eu", "asia", "global"] | None = None,
    max_price_usd: float | None = None,
    open_weights: bool | None = None,
    query: str | None = None,
    include_unlisted_languages: bool = False,
    sort: Literal["price", "name"] = "price",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Search active speech models. Filters combine (AND). Paged: pass next_offset to get more.

    language: BCP-47 code, e.g. "hi" or "en-GB". Only models that explicitly list it are returned, unless
    include_unlisted_languages=true also adds models that claim "many languages" without listing them. capability: one feature term, e.g. "speaker_diarization",
    "voice_cloning", "word_timestamps", "ssml". max_price_usd: upper bound on the normalized price (TTS per 1M
    characters, STT/STS per hour); models without a comparable USD price are excluded when it is set.
    sort="price" puts the cheapest first and unpriced models last.
    """
    cat = _cat()
    if capability and capability not in MODEL_CAPABILITIES:
        return {"error": f"unknown capability {capability!r}", "valid_capabilities": sorted(MODEL_CAPABILITIES)}
    rows = views.active_models(cat)
    if type:
        rows = [r for r in rows if r.model.type == type]
    if provider:
        rows = [r for r in rows if r.provider_id == provider]
    if language:
        rows = [r for r in rows if language_matches(language, [x for x in r.model.languages if x != "*"])
                or (include_unlisted_languages and "*" in r.model.languages)]
    if capability:
        rows = [r for r in rows if capability in r.model.capabilities]
    if region:
        rows = [r for r in rows if region in r.model.regions or "global" in r.model.regions]
    if open_weights is not None:
        rows = [r for r in rows if (r.model.open_weights is not None) == open_weights]
    if query:
        q = query.lower()
        rows = [r for r in rows if q in r.model.id.lower() or q in r.model.name.lower() or q in r.provider_id]

    def price(r) -> float:
        n = views.normalized_price(r.model)
        return n[0] if n else float("inf")
    if max_price_usd is not None:
        rows = [r for r in rows if price(r) <= max_price_usd]
    rows.sort(key=(lambda r: (price(r), r.provider_id, r.model.id)) if sort == "price"
              else (lambda r: (r.model.name.lower(), r.provider_id)))
    chunk, meta = _page(rows, limit, offset)
    return {**meta, "results": [_model_summary(cat, r) for r in chunk]}


@server.tool(annotations=READ_ONLY)
def get_model(provider: str, type: ModelType, model_id: str) -> dict[str, Any]:
    """Full record for one model: pricing (with variants and source URL), languages, capabilities, regions,
    interfaces, audio formats, limits, lifecycle and shutdown date, open-weights licence, provenance."""
    cat = _cat()
    r = views.find_model(cat, f"{provider}/{type}/{model_id}")
    if not r:
        return {"error": "model not found", "hint": "use search_models to find valid provider/type/model_id"}
    out = _model_summary(cat, r)
    out["record"] = r.model.model_dump(mode="json", exclude_none=True)
    return out


@server.tool(annotations=READ_ONLY)
def compare_models(models: list[str]) -> dict[str, Any]:
    """Compare up to 6 models side by side. Each item can be an exact key "provider/type/model_id" (from
    search_models) or a loose name like "deepgram nova-3" or "Cartesia Sonic 3"; unmatched items come back
    with "did you mean" suggestions."""
    cat = _cat()
    found, missing = [], []
    for ref in models[:6]:
        r, suggestions = resolve_model(cat, ref)
        if r:
            found.append(_model_summary(cat, r))
        else:
            missing.append({"query": ref, "did_you_mean": suggestions})
    url = _site() + "/compare?" + "&".join(f"m={m['key']}" for m in found) if found else None
    return {"models": found, "missing": missing, "compare_url": url}


@server.tool(annotations=READ_ONLY)
def estimate_cost(
    models: list[str],
    characters: int | None = None,
    audio_minutes: float | None = None,
    tts_chars_per_minute: int = 900,
    tts_share: float = 1.0,
) -> dict[str, Any]:
    """Cost in USD for a workload, computed here so no unit conversion is left to the model.

    models: keys or loose names (up to 6). characters: text to synthesize (TTS). audio_minutes: audio to
    transcribe (STT/STS), or for TTS the minutes of speech to produce (converted with tts_chars_per_minute,
    default 900 chars ≈ 150 words/min). Passing an STT and a TTS model with audio_minutes gives a voice-agent
    pipeline estimate: STT transcribes all audio_minutes, TTS speaks tts_share of them (e.g. 0.5 if the agent
    talks half the time); "total_usd" sums the models (LLM and telephony not included). Uses each model's headline
    pay-as-you-go price; volume discounts, free tiers and plan prices (see get_model) are not applied.
    """
    cat = _cat()
    if characters is None and audio_minutes is None:
        return {"error": "pass characters and/or audio_minutes"}
    lines, missing, total, complete = [], [], 0.0, True
    for ref in models[:6]:
        r, suggestions = resolve_model(cat, ref)
        if not r:
            missing.append({"query": ref, "did_you_mean": suggestions})
            continue
        m, norm = r.model, views.normalized_price(r.model)
        line = {"key": views.model_key(r), "name": m.name, "type": str(m.type), "price": views.price_label(m)}
        if m.type == "tts":
            share = max(0.0, min(float(tts_share), 1.0))
            chars = characters if characters is not None else int(audio_minutes * share * tts_chars_per_minute)
            line["characters"] = chars
            line["assumption"] = None if characters is not None else (
                f"{tts_chars_per_minute} characters per minute" + (f", speaking {share:.0%} of the time" if share < 1 else ""))
            cost = norm[0] * chars / 1_000_000 if norm else None
        else:
            if audio_minutes is None:
                line["note"] = "needs audio_minutes"
                cost = None
            else:
                line["audio_minutes"] = audio_minutes
                cost = norm[0] * audio_minutes / 60 if norm else None
        if cost is None and "note" not in line:
            line["note"] = _price_note(cat, r.provider_id, m) or "no comparable USD price"
        line["cost_usd"] = round(cost, 4) if cost is not None else None
        if cost is None:
            complete = False
        else:
            total += cost
        line["price_source"] = m.pricing.source_url if m.pricing else None
        lines.append(line)
    return {"lines": lines, "total_usd": round(total, 4) if lines else None, "total_complete": complete and bool(lines),
            "missing": missing}


@server.tool(annotations=READ_ONLY)
def find_alternatives(model: str, limit: int = 10) -> dict[str, Any]:
    """Replacements for a model (e.g. one that is shutting down): active models of the same type, ranked by how
    many of its explicitly listed languages they cover, then shared features, then how close the price is. The
    provider's own announced successor, if any, comes first. model: key or loose name."""
    cat = _cat()
    r, suggestions = resolve_model(cat, model)
    if not r:
        return {"error": "model not found", "did_you_mean": suggestions}
    m = r.model
    langs = {views.base_language(x) for x in m.languages if x != "*"}
    caps, norm = set(m.capabilities), views.normalized_price(m)
    successor = m.meta.get("replacement") if isinstance(m.meta, dict) else None
    cands = []
    for c in views.active_models(cat):
        cm = c.model
        if cm.type != m.type or c is r or cm.eol_date or (c.provider_id == r.provider_id and cm.id == m.id):
            continue
        cl = {views.base_language(x) for x in cm.languages if x != "*"}
        covered = len(langs & cl) if langs else None
        cn = views.normalized_price(cm)
        gap = abs(math.log(cn[0] / norm[0])) if cn and norm and cn[0] > 0 and norm[0] > 0 else math.inf
        announced = bool(successor) and c.provider_id == r.provider_id and successor.split()[0] in cm.id
        cands.append((announced, covered, len(caps & set(cm.capabilities)), gap, c))
    featured = set(views.COMPARE_PROVIDERS)                 # widely used providers win ties, as on /alternatives
    cands.sort(key=lambda x: (not x[0], -(x[1] or 0), -x[2], x[4].provider_id not in featured, x[3], x[4].model.id))
    chunk = cands[:_limit(limit)]
    return {
        "model": _model_summary(cat, r),
        "announced_replacement": successor,
        "alternatives": [{**_model_summary(cat, c),
                          "announced_replacement": a,
                          "languages_covered": f"{cov}/{len(langs)}" if cov is not None else None,
                          "shared_features": f"{sh}/{len(caps)}" if caps else None}
                         for a, cov, sh, _gap, c in chunk],
    }


@server.tool(annotations=READ_ONLY)
def search_voices(
    provider: str | None = None,
    language: str | None = None,
    gender: Literal["male", "female", "neutral"] | None = None,
    model: str | None = None,
    has_sample: bool | None = None,
    query: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Search stock voices (15,000+, so results are compact and paged: pass next_offset for more).
    model: a model id of that provider (voices compatible with it). has_sample=true returns only voices with
    an audio preview URL."""
    cat = _cat()
    rows = views.active_voices(cat)
    if provider:
        rows = [r for r in rows if r.provider_id == provider]
    if model:
        rows = [r for r in rows if "*" in r.voice.compatible_models or model in r.voice.compatible_models]
    if language:
        rows = [r for r in rows if language_matches(language, r.voice.languages)]
    if gender:
        rows = [r for r in rows if r.voice.gender == gender]
    if has_sample:
        rows = [r for r in rows if r.voice.preview_url or r.voice.previews]
    if query:
        q = query.lower()
        rows = [r for r in rows if q in r.voice.name.lower() or q in (r.voice.description or "").lower()
                or q in (r.voice.accent or "").lower()]
    chunk, meta = _page(rows, limit, offset)
    out = []
    for r in chunk:
        v = r.voice
        sample = views.voice_sample(v, language)
        desc = v.description or None
        out.append({"provider": r.provider_id, "id": v.id, "name": v.name, "gender": v.gender, "accent": v.accent,
                    "languages": v.languages[:8] + ([f"+{len(v.languages) - 8} more"] if len(v.languages) > 8 else []),
                    "compatible_models": v.compatible_models[:5] + (["…"] if len(v.compatible_models) > 5 else []),
                    "sample_url": sample.url if sample else None,
                    "description": (desc[:140] + "…") if desc and len(desc) > 140 else desc})
    return {**meta, "results": out,
            "browse_url": _site() + "/voices" + (f"?provider={provider}" if provider else "")}


@server.tool(annotations=READ_ONLY)
def list_providers(type: ModelType | None = None, include_retired: bool = False) -> dict[str, Any]:
    """Providers in the catalog with model and voice counts, headquarters and access model. Retired providers
    (shut down or no longer sold) are included only when include_retired=true, with their retirement date."""
    cat = _cat()
    out = []
    for s in views.provider_summaries(cat):
        if s.status != "active" and not include_retired:
            continue
        if type and type not in s.types:
            continue
        out.append({"id": s.id, "name": s.name, "status": s.status, "types": s.types, "models": s.models,
                    "voices": s.voices, "headquarters": s.headquarters, "access": s.access,
                    "retired_on": s.retired_on, "url": f"{_site()}/providers/{s.id}"})
    return {"total": len(out), "providers": out}


@server.tool(annotations=READ_ONLY)
def recent_changes(provider: str | None = None, kind: str | None = None, limit: int = 30) -> dict[str, Any]:
    """Latest catalog changes, newest first: price changes, shutdown announcements, deprecations, models added.
    kind: one of price_changed, price_published, shutdown_announced, model_deprecated, model_removed, now_ga,
    model_added, provider_added, provider_retired."""
    if kind and kind not in KIND_LABELS:
        return {"error": f"unknown kind {kind!r}", "valid_kinds": sorted(KIND_LABELS)}
    items = [c for c in load_changes(settings.data_path)
             if (not provider or c.provider_id == provider) and (not kind or c.kind == kind)]
    n = _limit(limit)
    return {"total": len(items), "feed_url": _site() + "/changes.xml", "changes": [
        {"date": c.date, "kind": c.kind, "label": KIND_LABELS.get(c.kind, c.kind), "provider": c.provider_id,
         "model": c.model_key or None, "before": c.before or None, "after": c.after or None,
         "url": f"{_site()}/models/{c.model_key}" if c.model_id else f"{_site()}/providers/{c.provider_id}"}
        for c in items[:n]]}


def asgi_app():
    """The Starlette app holding the /mcp route. Public and read-only: DNS-rebinding protection (meant for
    servers on a user's own machine) is off so requests to voicedex.dev aren't rejected by Host."""
    return server.streamable_http_app(
        streamable_http_path="/mcp", stateless_http=True, json_response=True,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )


TOOLS = (search_models, get_model, compare_models, estimate_cost, find_alternatives, search_voices,
         list_providers, recent_changes)


def tool_docs() -> list[tuple[str, str]]:
    """(name, first sentence of the docstring) for the human-readable /mcp page."""
    return [(f.__name__, (f.__doc__ or "").strip().split("\n")[0]) for f in TOOLS]
