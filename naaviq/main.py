"""Open voice provider registry — public read-only API over the git-backed catalog in data/."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from naaviq.catalog.store import Catalog
from naaviq.config import settings
from naaviq.limiter import limiter
from naaviq.routers import catalog, providers
from naaviq.web import routes as web

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    cat = Catalog.load(settings.data_path)
    app.state.catalog = cat
    log.info("catalog_loaded", providers=len(cat.providers), models=len(cat.models),
             voices=len(cat.voices), etag=cat.etag)
    yield


app = FastAPI(
    title="Voice Provider Registry",
    description="Open catalog of speech-to-text and text-to-speech providers, models and voices.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

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


@app.get("/health", tags=["meta"])
async def health(request: Request):
    cat = request.app.state.catalog
    return {"status": "ok", "providers": len(cat.providers), "etag": cat.etag.strip('"')}
