"""Server-rendered catalog pages: home, providers, models, voices, search."""

from __future__ import annotations

import math
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates

from voicedex.catalog.schema import MODEL_CAPABILITIES
from voicedex.catalog.store import Catalog, language_matches
from voicedex.config import settings
from voicedex.routers._filters import get_catalog
from voicedex.web import views

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


_ASSETS: dict = {}


def _asset_version() -> str:
    """Content hash of the static CSS/JS, appended to their URLs so a deploy is never served stale assets
    (they're cached for 5 minutes by browsers and the CDN). Recomputed only when a file's mtime changes."""
    import hashlib
    static = Path(__file__).parent / "static"
    stamp = tuple((static / n).stat().st_mtime_ns for n in ("site.css", "site.js"))
    if _ASSETS.get("stamp") != stamp:
        h = hashlib.sha1(b"".join((static / n).read_bytes() for n in ("site.css", "site.js")))
        _ASSETS.update(stamp=stamp, v=h.hexdigest()[:10])
    return _ASSETS["v"]

templates.env.globals.update(
    site_name=settings.site_name,
    site_url=settings.site_url.rstrip("/"),
    asset_v=_asset_version,
    language_name=views.language_name,
    price_label=views.price_label,
    model_url=views.model_url,
    model_key=views.model_key,
    variant_label=views.variant_label,
    duration=views.duration,
    lang_count=views.lang_count,
    voice_chips=views.voice_chips,
    FEATURE_LABELS=views.FEATURE_LABELS,
    feature_vocab=views.feature_vocab,
    INTERFACE_LABELS=views.INTERFACE_LABELS,
    heat_level=views.heat_level,
    TYPE_LABELS=views.TYPE_LABELS,
    TYPE_SHORT=views.TYPE_SHORT,
    ACCESS_LABELS=views.ACCESS_LABELS,
    country_name=views.country_name,
)

router = APIRouter(include_in_schema=False)

VOICES_PER_PAGE = 60
MAX_COMPARE = 6


def _q(request: Request, name: str) -> str:
    return (request.query_params.get(name) or "").strip()


def _qs(f: dict, **changes) -> str:
    """Query string for the current filters with some keys changed (None/"" removes a key)."""
    from urllib.parse import urlencode
    merged = {**f, **changes}
    return urlencode({k: v for k, v in merged.items() if v})


_TOKEN_LABEL = {"type": "type", "language": "language", "capability": "feature", "provider": "provider",
                "status": "status", "q": "name", "gender": "gender", "preview": "sample", "model": "model"}


def _token_value(key: str, value: str, catalog: Catalog) -> str:
    if key == "type":
        return views.TYPE_SHORT.get(value, value)
    if key == "language":
        return views.language_name(value)
    if key == "capability":
        return views.FEATURE_LABELS.get(value, value)
    if key == "provider":
        pd = catalog.providers.get(value)
        return pd.provider.name if pd else value
    if key == "status":
        return {"ending": "shutting down", "beta": "beta / preview"}.get(value, value)
    if key == "preview":
        return "has sample"
    return value


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, catalog: Catalog = Depends(get_catalog)):
    map_type = _q(request, "map") if _q(request, "map") in views.TYPE_LABELS else ""
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
    today = date.today()
    live_ids = {s.id for s in live}
    upcoming_eol = sorted(
        (r for r in views.active_models(catalog) if r.model.eol_date and r.model.eol_date >= today
         and r.provider_id in live_ids),
        key=lambda r: r.model.eol_date,
    )
    return templates.TemplateResponse(request, "home.html", {
        "live": live,
        "retired": [s for s in summaries if s.status != "active"],
        "coverage": views.coverage_map(catalog, model_type=map_type),
        "map_type": map_type,
        "n_models": len(views.active_models(catalog)),
        "n_voices": len(views.active_voices(catalog)),
        "recent": recent,
        "upcoming_eol": upcoming_eol,
        "timeline": views.shutdown_timeline(upcoming_eol, today),
        "today": today,
        "spectrum": views.price_spectrum(catalog),
        "n_voices_live": sum(s.voices for s in live),
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
        "positions": views.price_positions(views.price_spectrum(catalog)),
    })


@router.get("/models", response_class=HTMLResponse)
async def models_page(request: Request, catalog: Catalog = Depends(get_catalog)):
    f = {k: _q(request, k) for k in ("type", "language", "capability", "provider", "q", "sort", "status")}
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
    if f["status"] == "ending":
        rows = [r for r in rows if r.model.eol_date]
    if f["status"] == "beta":
        rows = [r for r in rows if str(getattr(r.model.lifecycle, "value", r.model.lifecycle)) in ("alpha", "beta")]
    if f["status"] == "ending" and f["sort"] != "price":
        rows.sort(key=lambda r: (r.model.eol_date, r.provider_id, r.model.id))
    elif f["sort"] == "price":
        rows.sort(key=lambda r: (views.normalized_price(r.model) or (math.inf,))[0])
    else:
        rows.sort(key=lambda r: (r.provider_id, r.model.type, not r.model.is_default, r.model.id))
    filtered = any(v for k, v in f.items() if k != "sort")
    keys = {views.model_key(r) for r in rows}
    spectrum = [b for b in views.price_spectrum(catalog, highlight=keys if filtered else None)
                if not filtered or any(it.state == "on" for col in b.columns for it in col)]
    tokens = [(k, _TOKEN_LABEL[k], _token_value(k, v, catalog)) for k, v in f.items() if v and k in _TOKEN_LABEL]
    return templates.TemplateResponse(request, "models.html", {
        "rows": rows, "f": f, "filtered": filtered, "spectrum": spectrum, "tokens": tokens,
        "positions": views.price_positions(views.price_spectrum(catalog)),
        "qs": lambda **changes: _qs(f, **changes),
        "languages": views.language_options(catalog),
        "capabilities": sorted(MODEL_CAPABILITIES, key=lambda c: views.FEATURE_LABELS.get(c, c)),
        "providers": [s for s in views.provider_summaries(catalog) if s.models],
        "names": {pid: pd.provider.name for pid, pd in catalog.providers.items()},
    })


@router.get("/voices", response_class=HTMLResponse)
async def voices_page(request: Request, catalog: Catalog = Depends(get_catalog)):
    f = {k: _q(request, k) for k in ("provider", "model", "language", "gender", "q", "preview")}
    rows = views.active_voices(catalog)
    if f["provider"]:
        rows = [r for r in rows if r.provider_id == f["provider"]]
    if f["provider"] and f["model"]:
        rows = [r for r in rows if "*" in r.voice.compatible_models or f["model"] in r.voice.compatible_models]
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
    rows = sorted(rows, key=lambda r: r.voice.preview_url is None)   # stable: samples first
    try:
        page = max(1, int(_q(request, "page") or 1))
    except ValueError:
        page = 1
    pages = max(1, math.ceil(len(rows) / VOICES_PER_PAGE))
    page = min(page, pages)
    return templates.TemplateResponse(request, "voices.html", {
        "rows": rows[(page - 1) * VOICES_PER_PAGE: page * VOICES_PER_PAGE],
        "total": len(rows), "page": page, "pages": pages, "f": f,
        "tokens": [(k, _TOKEN_LABEL[k], _token_value(k, v, catalog)) for k, v in f.items() if v and k in _TOKEN_LABEL],
        "qs": lambda **changes: _qs({**f, "page": str(page) if page > 1 else ""}, **{k: (str(v) if v else v) for k, v in changes.items()}),
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
    lang_hits = [(code, name) for code, name in views.language_options(catalog)
                 if needle and (needle == name.lower() or needle == code)]
    feature_hits = [(c, label) for c, label in views.FEATURE_LABELS.items()
                    if needle and len(needle) > 2 and (needle in label.lower() or needle in c)]
    return templates.TemplateResponse(request, "search.html", {
        "q": q, "providers": providers, "models": models, "voices": voices, "lang_hits": lang_hits, "feature_hits": feature_hits,
        "names": {pid: pd.provider.name for pid, pd in catalog.providers.items()},
    })


@router.get("/models/{provider_id}/{model_type}/{model_id:path}", response_class=HTMLResponse)
async def model_page(request: Request, provider_id: str, model_type: str, model_id: str,
                     catalog: Catalog = Depends(get_catalog)):
    row = views.find_model(catalog, f"{provider_id}/{model_type}/{model_id}")
    if not row:
        raise HTTPException(404, "Model not found")
    pd = catalog.providers[provider_id]
    siblings = sorted((r for r in views.active_models(catalog, provider_id)
                       if r.model.type == row.model.type and r.model.id != row.model.id),
                      key=lambda r: (r.model.eol_date is not None, not r.model.is_default, r.model.id))
    voices = views.voices_for_model(catalog, row)
    replacement = None
    rep_id = row.model.meta.get("replacement") if isinstance(row.model.meta, dict) else None
    if rep_id:
        replacement = next((views.find_model(catalog, f"{provider_id}/{t}/{rep_id}") for t in
                            (row.model.type, "stt", "tts", "sts") if views.find_model(catalog, f"{provider_id}/{t}/{rep_id}")), None)
    return templates.TemplateResponse(request, "model.html", {
        "r": row, "m": row.model, "p": pd.provider, "siblings": siblings[:12],
        "voice_count": len(voices), "voice_sample": sorted(voices, key=lambda v: v.voice.preview_url is None)[:6],
        "replacement": replacement,
        "lang_groups": views.language_groups(row.model.languages),
        "spectrum": [b for b in views.price_spectrum(catalog, highlight={views.model_key(row)})
                     if row.model.type in next(t for i, t, _, _ in views.SPECTRUM_BANDS if i == b.id)],
        "rank": views.price_rank(catalog, row),
        "today": date.today(),
        "api_path": f"/v1/providers/{provider_id}/models/{quote(row.model.id, safe='')}",
    })


@router.get("/compare", response_class=HTMLResponse)
async def compare_page(request: Request, catalog: Catalog = Depends(get_catalog)):
    keys = list(dict.fromkeys(k for k in request.query_params.getlist("m") if k))[:MAX_COMPARE]
    rows = [r for r in (views.find_model(catalog, k) for k in keys) if r]
    lang = _q(request, "language")
    names = {pid: pd.provider.name for pid, pd in catalog.providers.items()}
    options = sorted(views.active_models(catalog), key=lambda r: (names[r.provider_id].lower(), r.model.type, r.model.id))
    return templates.TemplateResponse(request, "compare.html", {
        "rows": rows, "keys": [views.model_key(r) for r in rows], "names": names,
        "table": _grouped(views.compare_table(rows, names, lang)) if rows else [],
        "language": lang, "languages": views.language_options(catalog),
        "options": [r for r in options if views.model_key(r) not in keys],
        "max_compare": MAX_COMPARE, "missing": [k for k in keys if not views.find_model(catalog, k)],
        "spectrum": views.price_spectrum(catalog, highlight={views.model_key(r) for r in rows}) if rows else [],
    })


def _grouped(table: list) -> list[tuple[str, list]]:
    """Group compare rows by section, keeping first-seen order."""
    out: dict[str, list] = {}
    for row in table:
        out.setdefault(row.group, []).append(row)
    return list(out.items())


@router.get("/docs", response_class=HTMLResponse)
async def api_docs(request: Request):
    """Themed API reference (Scalar) over the app's own OpenAPI schema."""
    return templates.TemplateResponse(request, "docs.html", {})


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    site = settings.site_url.rstrip("/")
    return ("User-agent: *\n"
            "Disallow: /search\n"            # result pages for arbitrary queries
            "Disallow: /compare\n"           # unbounded combinations of models
            "Disallow: /v1/\n"               # the JSON API
            f"\nSitemap: {site}/sitemap.xml\n")


@router.get("/sitemap.xml")
async def sitemap(catalog: Catalog = Depends(get_catalog)):
    site = settings.site_url.rstrip("/")
    paths = ["/", "/models", "/voices", "/docs"]
    paths += [f"/providers/{pid}" for pid in sorted(catalog.providers)]
    paths += sorted(views.model_url(r) for r in views.active_models(catalog))
    body = "".join(f"<url><loc>{escape(site + p)}</loc></url>" for p in paths)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'
    return Response(xml, media_type="application/xml")


@router.get("/redoc")
async def redoc_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/docs", status_code=301)
