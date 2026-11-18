"""Voicedex — open voice AI catalog — public read-only API over the git-backed catalog in data/."""

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from voicedex import mcp_server
from voicedex.catalog.store import Catalog
from voicedex.config import settings
from voicedex.limiter import limiter
from voicedex.routers import catalog, providers
from voicedex.web import routes as web

log = structlog.get_logger()
# The MCP SDK logs "Terminating session: None" at INFO for every stateless request; keep warnings only.
logging.getLogger("mcp.server.streamable_http").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cat = Catalog.load(settings.data_path)
    app.state.catalog = cat
    log.info("catalog_loaded", providers=len(cat.providers), models=len(cat.models),
             voices=len(cat.voices), etag=cat.etag)
    async with mcp_server.server.session_manager.run():      # the /mcp endpoint's task group
        yield


API_DESCRIPTION = """
An open, read-only catalog of voice AI: every speech-to-text, text-to-speech and speech-to-speech
model and stock voice from the major providers, with languages, features, prices and shutdown dates.
Data is read from each provider's API or documentation, reviewed, and versioned in git.

## Quickstart

No key, no sign-up. Every endpoint is a plain `GET`.

```bash
# Speech-to-text models that support Hindi and speaker diarization
curl "https://<host>/v1/models?type=stt&language=hi&capabilities=speaker_diarization"

# British female voices from one provider
curl "https://<host>/v1/providers/elevenlabs/voices?gender=female&accent=british"

# Everything, in one response
curl "https://<host>/v1/catalog.json"
```

## Conventions

- **Languages** are BCP-47 (`en-US`, `hi-IN`). `language=en` matches every English locale; `*` on a
  record means "many languages, not enumerated" and always matches.
- **Capabilities** use a fixed vocabulary, e.g. `word_timestamps`, `speaker_diarization`, `voice_cloning`.
  Multiple values must all match.
- **Prices** are list prices as published: `price_usd` per `unit`, plan tiers in `variants`, and
  `currency` + `price` for providers that only publish in another currency (never converted).
- **Lifecycle**: `alpha`, `beta`, `ga`, `deprecated`. A model with an announced shutdown date carries
  `eol_date` and is listed until that day.
- **IDs**: `id` is a stable UUID; `model_id` / `voice_id` is the exact string to send to the provider.

## Caching and limits

Every `/v1` response carries one catalog-wide `ETag`; send it back as `If-None-Match` to get
`304 Not Modified`. Responses are cacheable for five minutes. Polling for changes? Use
`updated_since` (it includes deprecations). Requests are rate limited per client IP.
"""

OPENAPI_TAGS = [
    {"name": "Models & voices", "description": "Search models and voices across every provider."},
    {"name": "Providers", "description": "Providers and their models and voices, one provider at a time."},
    {"name": "Bulk export", "description": "The whole catalog in one response, for offline use or mirroring."},
    {"name": "Meta", "description": "Service health."},
]

app = FastAPI(
    title=f"{settings.site_name} API",
    summary="Open catalog of speech-to-text, text-to-speech and speech-to-speech models and voices.",
    description=API_DESCRIPTION,
    version="1.0.0",
    openapi_tags=OPENAPI_TAGS,
    docs_url=None,      # /docs is our themed reference (voicedex/web/routes.py)
    redoc_url=None,
    lifespan=lifespan,
)

def _openapi_with_examples() -> dict:
    """OpenAPI document with real-data examples from the loaded catalog (built once per process)."""
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    from voicedex.openapi_examples import inject_examples
    spec = get_openapi(title=app.title, version=app.version, summary=app.summary, description=app.description,
                       routes=app.routes, tags=app.openapi_tags)
    catalog = getattr(app.state, "catalog", None)
    if catalog is not None:
        inject_examples(spec, catalog)
        app.openapi_schema = spec        # cache only once the catalog is loaded
    return spec


app.openapi = _openapi_with_examples
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],        # POST only for /mcp (browser-based MCP clients); the API is GET-only
    allow_headers=["*"],
    expose_headers=["ETag", "Mcp-Session-Id"],
)


@app.middleware("http")
async def etag_cache(request: Request, call_next):
    """The catalog only changes on deploy, so one ETag covers every /v1 response, and every page can be
    cached for a few minutes (by browsers and by a CDN in front, which serves visits while the origin
    is scaled to zero)."""
    if request.method != "GET":
        return await call_next(request)
    is_api = request.url.path.startswith("/v1")
    etag = request.app.state.catalog.etag
    if is_api and request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response = await call_next(request)
    if response.status_code == 200 and request.url.path != "/health":
        if is_api:
            response.headers["ETag"] = etag
        response.headers.setdefault("Cache-Control", "public, max-age=300")
    return response


@app.middleware("http")
async def strip_trailing_slash(request: Request, call_next):
    """`/models/` → 301 `/models`. Starlette's own slash redirect is a 307 (temporary), which search engines
    don't consolidate; no route here ends in a slash, so a permanent redirect is always right."""
    path = request.url.path
    if request.method in ("GET", "HEAD") and len(path) > 1 and path.endswith("/"):
        target = "/" + path.strip("/")             # also collapses a leading "//" (no protocol-relative redirect)
        if request.url.query:
            target += "?" + request.url.query
        return RedirectResponse(target, status_code=301)
    return await call_next(request)


@app.middleware("http")
async def mcp_get(request: Request, call_next):
    """GET /mcp: the MCP SDK would hold the request open as an SSE stream, which a stateless server never uses.
    MCP clients asking for a stream get 405 (as the spec allows); browsers and crawlers get the setup page."""
    if request.url.path == "/mcp" and request.method in ("GET", "HEAD"):
        if "text/event-stream" in request.headers.get("accept", ""):
            return Response(status_code=405, headers={"Allow": "POST"})
        return web.templates.TemplateResponse(request, "mcp.html", {"tools": mcp_server.tool_docs()})
    return await call_next(request)


# Outermost: compress responses (catalog.json is ~8 MB of JSON; gzip cuts transfer time and egress).
app.add_middleware(GZipMiddleware, minimum_size=1024)


app.include_router(providers.router, prefix="/v1")
app.include_router(catalog.router, prefix="/v1")
app.include_router(web.router)

# Remote MCP server (Streamable HTTP) at /mcp: the SDK's route, added to this app so it shares the lifespan,
# middleware and 404 handling. The SDK app must be built before the session manager exists.
_mcp_app = mcp_server.asgi_app()
app.router.routes.extend(r for r in _mcp_app.routes if getattr(r, "path", "") == "/mcp")


@app.exception_handler(404)
async def not_found(request: Request, exc):
    """HTML 404 for site pages; JSON for the API."""
    detail = getattr(exc, "detail", "Not Found")
    if request.url.path.startswith(("/v1", "/static", "/docs", "/redoc", "/openapi")):
        return JSONResponse({"detail": detail}, status_code=404)
    return web.templates.TemplateResponse(request, "404.html", {"detail": detail}, status_code=404)
app.mount("/static", StaticFiles(directory=str(web.Path(web.__file__).parent / "static")), name="static")


@app.get("/health", tags=["Meta"], summary="Health check")
async def health(request: Request, response: Response):
    cat = request.app.state.catalog
    response.headers["Cache-Control"] = "no-store"     # never served from a CDN cache
    return {"status": "ok", "providers": len(cat.providers), "etag": cat.etag.strip('"')}
