"""Server-rendered catalog pages: home, providers, models, voices, search."""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from naaviq.catalog.schema import MODEL_CAPABILITIES
from naaviq.catalog.store import Catalog, language_matches
from naaviq.config import settings
from naaviq.routers._filters import get_catalog
from naaviq.web import views

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals.update(
    site_name=settings.site_name,
    language_name=views.language_name,
    price_label=views.price_label,
    heat_level=views.heat_level,
    TYPE_LABELS=views.TYPE_LABELS,
    TYPE_SHORT=views.TYPE_SHORT,
)

router = APIRouter(include_in_schema=False)

VOICES_PER_PAGE = 60


def _q(request: Request, name: str) -> str:
    return (request.query_params.get(name) or "").strip()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, catalog: Catalog = Depends(get_catalog)):
    summaries = views.provider_summaries(catalog)
    live = [s for s in summaries if s.status == "active"]
    # "Recently changed" only means something once there's history beyond the initial import.
    models = views.active_models(catalog)
    first_seen = Counter(r.model.first_seen for r in models)
    initial_import = first_seen.most_common(1)[0][0] if first_seen else None
    recent = sorted(
        (r for r in models if r.model.updated_at and not (
            r.model.first_seen == initial_import and r.model.updated_at == initial_import)),
        key=lambda r: (r.model.updated_at, r.model.first_seen == r.model.updated_at), reverse=True,
    )[:12]
    upcoming_eol = sorted(
        (r for r in views.active_models(catalog) if r.model.eol_date),
        key=lambda r: r.model.eol_date,
    )
    return templates.TemplateResponse(request, "home.html", {
        "live": live,
        "retired": [s for s in summaries if s.status != "active"],
        "coverage": views.coverage_map(catalog),
        "n_models": len(views.active_models(catalog)),
        "n_voices": len(views.active_voices(catalog)),
        "recent": recent,
        "upcoming_eol": upcoming_eol,
        "names": {pid: pd.provider.name for pid, pd in catalog.providers.items()},
    })


@router.get("/providers/{provider_id}", response_class=HTMLResponse)
async def provider_page(request: Request, provider_id: str, catalog: Catalog = Depends(get_catalog)):
    pd = catalog.providers.get(provider_id)
    if not pd:
        raise HTTPException(404, "Provider not found")
    models = sorted(views.active_models(catalog, provider_id),
                    key=lambda r: (r.model.type, r.model.eol_date is not None, not r.model.is_default,
                                   r.model.name.lower()))
    summary = next(s for s in views.provider_summaries(catalog) if s.id == provider_id)
    voices = views.active_voices(catalog, provider_id)
    return templates.TemplateResponse(request, "provider.html", {
        "p": pd.provider, "summary": summary, "models": models,
        "voice_count": len(voices), "voice_sample": voices[:12],
        "deprecated": [r for r in catalog.models if r.provider_id == provider_id and r.model.deprecated_at],
    })


@router.get("/models", response_class=HTMLResponse)
async def models_page(request: Request, catalog: Catalog = Depends(get_catalog)):
    f = {k: _q(request, k) for k in ("type", "language", "capability", "provider", "q", "sort")}
    rows = views.active_models(catalog)
    if f["type"] in views.TYPE_LABELS:
        rows = [r for r in rows if r.model.type == f["type"]]
    if f["provider"]:
        rows = [r for r in rows if r.provider_id == f["provider"]]
    if f["language"]:
        rows = [r for r in rows if language_matches(f["language"], r.model.languages)]
    if f["capability"]:
        rows = [r for r in rows if f["capability"] in r.model.capabilities]
    if f["q"]:
        needle = f["q"].lower()
        rows = [r for r in rows if needle in r.model.id.lower() or needle in r.model.name.lower()
                or needle in (r.model.description or "").lower() or needle in r.provider_id]
    if f["sort"] == "price":
        rows.sort(key=lambda r: (views.normalized_price(r.model) or (math.inf,))[0])
    else:
        rows.sort(key=lambda r: (r.provider_id, r.model.type, not r.model.is_default, r.model.id))
    return templates.TemplateResponse(request, "models.html", {
        "rows": rows, "f": f,
        "languages": views.language_options(catalog),
        "capabilities": sorted(MODEL_CAPABILITIES),
        "providers": [s for s in views.provider_summaries(catalog) if s.models],
        "names": {pid: pd.provider.name for pid, pd in catalog.providers.items()},
    })


@router.get("/voices", response_class=HTMLResponse)
async def voices_page(request: Request, catalog: Catalog = Depends(get_catalog)):
    f = {k: _q(request, k) for k in ("provider", "language", "gender", "q", "preview")}
    rows = views.active_voices(catalog)
    if f["provider"]:
        rows = [r for r in rows if r.provider_id == f["provider"]]
    if f["language"]:
        rows = [r for r in rows if language_matches(f["language"], r.voice.languages)]
    if f["gender"] in ("male", "female", "neutral"):
        rows = [r for r in rows if r.voice.gender == f["gender"]]
    if f["preview"]:
        rows = [r for r in rows if r.voice.preview_url]
    if f["q"]:
        needle = f["q"].lower()
        rows = [r for r in rows if needle in r.voice.name.lower() or needle in r.voice.id.lower()
                or needle in (r.voice.description or "").lower() or needle in (r.voice.accent or "")
                or any(needle in t.lower() for t in r.voice.use_cases + r.voice.tags)]
    try:
        page = max(1, int(_q(request, "page") or 1))
    except ValueError:
        page = 1
    pages = max(1, math.ceil(len(rows) / VOICES_PER_PAGE))
    page = min(page, pages)
    return templates.TemplateResponse(request, "voices.html", {
        "rows": rows[(page - 1) * VOICES_PER_PAGE: page * VOICES_PER_PAGE],
        "total": len(rows), "page": page, "pages": pages, "f": f,
        "languages": views.language_options(catalog),
        "providers": [s for s in views.provider_summaries(catalog) if s.voices],
        "names": {pid: pd.provider.name for pid, pd in catalog.providers.items()},
    })


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, catalog: Catalog = Depends(get_catalog)):
    q = _q(request, "q")
    needle = q.lower()
    providers, models, voices = [], [], []
    if needle:
        providers = [s for s in views.provider_summaries(catalog)
                     if needle in s.name.lower() or needle in s.id]
        models = [r for r in views.active_models(catalog)
                  if needle in r.model.id.lower() or needle in r.model.name.lower()][:40]
        voices = [r for r in views.active_voices(catalog) if needle in r.voice.name.lower()][:40]
    lang_hits = [(code, name) for code, name in views.language_options(catalog) if needle and needle == name.lower()]
    return templates.TemplateResponse(request, "search.html", {
        "q": q, "providers": providers, "models": models, "voices": voices, "lang_hits": lang_hits,
        "names": {pid: pd.provider.name for pid, pd in catalog.providers.items()},
    })
