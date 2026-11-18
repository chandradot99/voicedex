"""Remote MCP server at /mcp: lets AI assistants (Claude, Cursor, ...) query the catalog directly.

Streamable HTTP, stateless, JSON responses, read-only. It reads the same in-memory Catalog the REST API and the
site serve (set in main's lifespan), so it adds no state and scales to zero like the rest of the app.
"""

from __future__ import annotations

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


def _model_summary(cat: Catalog, r) -> dict[str, Any]:
    m = r.model
    norm = views.normalized_price(m)
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
        "languages": "many" if "*" in m.languages else len({views.base_language(lang) for lang in m.languages}),
        "capabilities": sorted(m.capabilities),
        "streaming": any(str(i) in ("websocket", "webrtc") for i in m.interfaces),
        "open_weights": m.open_weights is not None,
        "lifecycle": str(m.lifecycle),
        "eol_date": m.eol_date.isoformat() if m.eol_date else None,
        "url": _site() + views.model_url(r),
    }


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
) -> dict[str, Any]:
    """Search active speech models. Filters combine (AND).

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
    n = _limit(limit)
    return {"total": len(rows), "returned": min(n, len(rows)),
            "results": [_model_summary(cat, r) for r in rows[:n]]}


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
    """Compare up to 6 models side by side. Each item is a key "provider/type/model_id" as returned by
    search_models (e.g. "deepgram/stt/nova-3-general")."""
    cat = _cat()
    found, missing = [], []
    for k in models[:6]:
        r = views.find_model(cat, k)
        (found.append(_model_summary(cat, r)) if r else missing.append(k))
    url = _site() + "/compare?" + "&".join(f"m={m['key']}" for m in found) if found else None
    return {"models": found, "missing": missing, "compare_url": url}


@server.tool(annotations=READ_ONLY)
def search_voices(
    provider: str | None = None,
    language: str | None = None,
    gender: Literal["male", "female", "neutral"] | None = None,
    model: str | None = None,
    has_sample: bool | None = None,
    query: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """Search stock voices. model: a model id of that provider (voices compatible with it). has_sample=true
    returns only voices with an audio preview URL."""
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
    n = _limit(limit)
    out = []
    for r in rows[:n]:
        v = r.voice
        sample = views.voice_sample(v, language)
        out.append({"provider": r.provider_id, "id": v.id, "name": v.name, "gender": v.gender, "accent": v.accent,
                    "languages": v.languages, "compatible_models": v.compatible_models,
                    "sample_url": sample.url if sample else None, "description": v.description})
    return {"total": len(rows), "returned": len(out), "results": out,
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


TOOLS = (search_models, get_model, compare_models, search_voices, list_providers, recent_changes)


def tool_docs() -> list[tuple[str, str]]:
    """(name, first sentence of the docstring) for the human-readable /mcp page."""
    return [(f.__name__, (f.__doc__ or "").strip().split("\n")[0]) for f in TOOLS]
