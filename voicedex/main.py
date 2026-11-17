"""Voicedex — open voice AI catalog — public read-only API over the git-backed catalog in data/."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from voicedex.catalog.store import Catalog
from voicedex.config import settings
from voicedex.limiter import limiter
from voicedex.routers import catalog, providers
from voicedex.web import routes as web

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    cat = Catalog.load(settings.data_path)
    app.state.catalog = cat
    log.info("catalog_loaded", providers=len(cat.providers), models=len(cat.models),
             voices=len(cat.voices), etag=cat.etag)
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
    version="2.0.0",
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
    allow_methods=["GET"],
    allow_headers=["*"],
    expose_headers=["ETag"],
)


@app.middleware("http")
async def etag_cache(request: Request, call_next):
    """The catalog only changes on deploy, so one ETag covers every /v1 response."""
    if request.method != "GET" or not request.url.path.startswith("/v1"):
        return await call_next(request)
    etag = request.app.state.catalog.etag
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response = await call_next(request)
    if response.status_code == 200:
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "public, max-age=300"
    return response


app.include_router(providers.router, prefix="/v1")
app.include_router(catalog.router, prefix="/v1")
app.include_router(web.router)


@app.exception_handler(404)
async def not_found(request: Request, exc):
    """HTML 404 for site pages; JSON for the API."""
    detail = getattr(exc, "detail", "Not Found")
    if request.url.path.startswith(("/v1", "/static", "/docs", "/redoc", "/openapi")):
        return JSONResponse({"detail": detail}, status_code=404)
    return web.templates.TemplateResponse(request, "404.html", {"detail": detail}, status_code=404)
app.mount("/static", StaticFiles(directory=str(web.Path(web.__file__).parent / "static")), name="static")


@app.get("/health", tags=["Meta"], summary="Health check")
async def health(request: Request):
    cat = request.app.state.catalog
    return {"status": "ok", "providers": len(cat.providers), "etag": cat.etag.strip('"')}
