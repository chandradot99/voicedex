"""Server-rendered catalog pages: home, providers, models, voices, search."""

from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from voicedex.catalog.schema import MODEL_CAPABILITIES
from voicedex.catalog.store import Catalog, language_matches
from voicedex.config import settings
from voicedex.routers._filters import get_catalog
from voicedex.web import views
from voicedex.web.changes import KIND_LABELS, load_changes

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

def _path_links(text: str) -> Markup:
    """Escape text, then link bare site paths like /changes (FAQ answers are plain text for JSON-LD)."""
    return Markup(re.sub(r"(?<![\w/])(/[a-z0-9][a-z0-9/-]*[a-z0-9])", r'<a href="\1">\1</a>', str(escape(text))))


templates.env.filters["path_links"] = _path_links
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
    pick_sample=views.voice_sample,
    FEATURE_LABELS=views.FEATURE_LABELS,
    feature_vocab=views.feature_vocab,
    INTERFACE_LABELS=views.INTERFACE_LABELS,
    heat_level=views.heat_level,
    TYPE_LABELS=views.TYPE_LABELS,
    TYPE_SHORT=views.TYPE_SHORT,
    ACCESS_LABELS=views.ACCESS_LABELS,
    country_name=views.country_name,
    report_url=views.report_url, VERIFICATION_DOC=views.VERIFICATION_DOC,
    monthly_cost=views.monthly_cost, money=views.money, compact_number=views.compact_number, plain_number=views.plain_number, USAGE=views.USAGE,
    is_realtime=views.is_realtime, licence_tier=views.licence_tier, licence_short=views.licence_short, free_quota_label=views.free_quota_label,
    connection_label=views.connection_label,
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
                "status": "status", "mode": "mode", "weights": "weights", "q": "name", "gender": "gender", "preview": "sample", "model": "model"}


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
    if key == "mode":
        return {"realtime": "realtime streaming"}.get(value, value)
    if key == "weights":
        return {"open": "open weights", "hosted": "hosted only"}.get(value, value)
    if key == "preview":
        return "has sample"
    return value


# The home page shows a slice of the coverage map (the full one is ~9k elements, too heavy for phones);
# /coverage has all of it.
HOME_MAP_PROVIDERS, HOME_MAP_LANGUAGES = 24, 32
LANDING_ROWS = 100            # cheapest-first rows on a landing page; the rest via "see all"


@router.get("/coverage", response_class=HTMLResponse)
async def coverage_page(request: Request, catalog: Catalog = Depends(get_catalog)):
    map_type = _q(request, "map") if _q(request, "map") in views.TYPE_LABELS else ""
    return templates.TemplateResponse(request, "coverage.html", {
        "coverage": views.coverage_map(catalog, model_type=map_type), "map_type": map_type,
    })


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
        "coverage": views.coverage_map(catalog, n_languages=HOME_MAP_LANGUAGES, model_type=map_type,
                                       n_providers=HOME_MAP_PROVIDERS),
        "coverage_providers": len(views.coverage_map(catalog, n_languages=1, model_type=map_type).rows),
        "map_type": map_type,
        "n_models": len(views.active_models(catalog)),
        "n_voices": len(views.active_voices(catalog)),
        "recent": recent,
        "upcoming_eol": upcoming_eol,
        "timeline": views.shutdown_timeline(upcoming_eol, today),
        "today": today,
        "spectrum": views.price_spectrum(catalog),
        "tasks": views.task_cards(catalog),
        "freshness": views.catalog_freshness(catalog, today),
        "n_voices_live": sum(s.voices for s in live),
        "names": {pid: pd.provider.name for pid, pd in catalog.providers.items()},
        "jsonld": _home_ld(catalog, len(views.active_models(catalog)), len(views.active_voices(catalog)), len(live)),
    })


# Profiles that are the same entity as voicedex.dev (schema.org sameAs). Only the project's own profiles belong
# here, not personal ones (add X/Bluesky once Voicedex has them).
SAME_AS = ["https://github.com/chandradot99/voicedex", "https://www.linkedin.com/company/voicedex"]


def _home_ld(catalog: Catalog, n_models: int, n_voices: int, n_providers: int) -> list[dict]:
    site = settings.site_url.rstrip("/")
    org_id = f"{site}/#organization"
    org = {"@context": "https://schema.org", "@type": "Organization", "@id": org_id, "name": settings.site_name,
           "url": site + "/", "logo": {"@type": "ImageObject", "url": f"{site}/static/logo.png",
                                       "width": 512, "height": 512},
           "description": "Open catalog of speech AI models, voices and prices.", "sameAs": SAME_AS}
    ref = {"@id": org_id}
    modified = views.last_modified(views.active_models(catalog))
    dataset = {
        "@context": "https://schema.org", "@type": "Dataset",
        "name": f"{settings.site_name}: catalog of speech AI models, voices and prices",
        "description": (f"Open catalog of {n_models} speech-to-text, text-to-speech and speech-to-speech models and "
                        f"{n_voices} voices from {n_providers} providers: supported languages, features, prices "
                        "(normalized per 1M characters or per hour), regions, lifecycle and shutdown dates. "
                        "Synced from provider APIs and documentation, reviewed, and versioned in git."),
        "url": site + "/", "sameAs": "https://github.com/chandradot99/voicedex",
        "keywords": ["speech-to-text", "text-to-speech", "speech-to-speech", "voice AI", "TTS", "STT", "ASR",
                     "pricing", "voices", "languages"],
        "license": "https://www.apache.org/licenses/LICENSE-2.0",
        "isAccessibleForFree": True, "creator": ref, "publisher": ref,
        "distribution": [{"@type": "DataDownload", "encodingFormat": "application/json",
                          "contentUrl": site + "/v1/catalog.json"}],
    }
    if modified:
        dataset["dateModified"] = modified.isoformat()
    website = {"@context": "https://schema.org", "@type": "WebSite", "@id": f"{site}/#website",
               "name": settings.site_name, "url": site + "/", "publisher": ref,
               "description": "Open catalog of speech AI models and voices: languages, features, prices and status."}
    return [org, website, dataset]


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
    faq = views.provider_faq(catalog, provider_id)
    return templates.TemplateResponse(request, "provider.html", {
        "p": pd.provider, "summary": summary, "models": models,
        "verified": views.verification_status(catalog, provider_id),
        "voice_count": len(voices), "voice_sample": voices[:12],
        "deprecated": [r for r in catalog.models if r.provider_id == provider_id and r.model.deprecated_at],
        "compare_with": [(views.provider_pair_slug(provider_id, other), catalog.providers[other].provider.name)
                         for other in views.compare_partners(catalog, provider_id)],
        "has_alternatives": provider_id in views.alternatives_subjects(catalog),
        "positions": views.price_positions(views.price_spectrum(catalog)),
        "faq": faq,
        "jsonld": [_breadcrumb_ld([("Home", "/"), (pd.provider.name, f"/providers/{provider_id}")])]
                  + ([_faq_ld(faq)] if faq else []),
    })


@router.get("/models", response_class=HTMLResponse)
async def models_page(request: Request, catalog: Catalog = Depends(get_catalog)):
    f = {k: _q(request, k) for k in ("type", "language", "capability", "provider", "q", "sort", "status", "mode", "weights")}
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
    if f["mode"] == "realtime":
        rows = [r for r in rows if views.is_realtime(r.model)]
    if f["weights"] in ("open", "hosted"):
        rows = [r for r in rows if (r.model.open_weights is not None) == (f["weights"] == "open")]
    if f["status"] == "beta":
        rows = [r for r in rows if str(getattr(r.model.lifecycle, "value", r.model.lifecycle)) in ("alpha", "beta")]
    if f["status"] == "ending" and f["sort"] != "price":
        rows.sort(key=lambda r: (r.model.eol_date, r.provider_id, r.model.id))
    elif f["sort"] == "price":
        rows.sort(key=lambda r: (views.normalized_price(r.model) or (math.inf,))[0])
    else:
        rows.sort(key=lambda r: (r.provider_id, r.model.type, not r.model.is_default, r.model.id))
    ctx = _models_context(catalog, rows, f, usage_raw=_q(request, "usage"))
    ctx["canonical_path"] = _models_canonical(catalog, f)
    return templates.TemplateResponse(request, "models.html", ctx)


def _models_context(catalog: Catalog, rows: list, f: dict, *, show_tokens: bool = True,
                    usage_raw: str | None = None) -> dict:
    filtered = any(v for k, v in f.items() if k != "sort")
    keys = {views.model_key(r) for r in rows}
    spectrum = [b for b in views.price_spectrum(catalog, highlight=keys if filtered else None)
                if not filtered or any(it.state == "on" for col in b.columns for it in col)]
    tokens = [(k, _TOKEN_LABEL[k], _token_value(k, v, catalog)) for k, v in f.items() if v and k in _TOKEN_LABEL]
    return {
        "rows": rows, "f": f, "filtered": filtered, "spectrum": spectrum, "tokens": tokens if show_tokens else [],
        "positions": views.price_positions(views.price_spectrum(catalog)),
        "qs": lambda **changes: _qs(f, **changes),
        "languages": views.language_options(catalog),
        "capabilities": sorted(MODEL_CAPABILITIES, key=lambda c: views.FEATURE_LABELS.get(c, c)),
        "providers": [s for s in views.provider_summaries(catalog) if s.models],
        "names": {pid: pd.provider.name for pid, pd in catalog.providers.items()},
        # Cost calculator: only when every row is one model type (a per-month figure needs one usage unit)
        "usage_type": f["type"] if f.get("type") in views.USAGE else None,
        "usage": views.parse_usage(f["type"], usage_raw) if f.get("type") in views.USAGE else None,
        "usage_hidden": [(k, v) for k, v in f.items() if v],
    }


def _models_canonical(catalog: Catalog, f: dict) -> str:
    """A /models filter that's exactly a landing page (type, type+language, type+feature) canonicalizes to it."""
    active = {k for k, v in f.items() if v and k != "sort"}
    page = None
    if active == {"type"}:
        page = views.find_landing(catalog, f["type"])
    elif active == {"type", "language"} and "-" not in f["language"]:
        page = views.find_landing(catalog, f["type"], "language", f["language"].lower())
    elif active == {"type", "capability"}:
        page = views.find_landing(catalog, f["type"], "feature", f["capability"])
    elif active == {"type", "mode"} and f["mode"] == "realtime":
        page = views.find_landing(catalog, f["type"], "realtime")
    elif active == {"type", "weights"} and f["weights"] == "open":
        page = views.find_landing(catalog, f["type"], "open")
    return page.url if page else "/models"


def _landing_page(type_slug: str):
    mtype = views.SLUG_TYPES[type_slug]

    async def page(request: Request, slug: str = "", catalog: Catalog = Depends(get_catalog)):
        landing = views.landing_pages(catalog).get(f"/{type_slug}" + (f"/{slug}" if slug else ""))
        if not landing:
            raise HTTPException(404, "Page not found")
        rows = views.landing_rows(catalog, landing)
        f = {"type": mtype, "language": landing.value if landing.kind == "language" else "",
             "capability": landing.value if landing.kind == "feature" else "",
             "provider": "", "q": "", "sort": "price", "status": "",
             "mode": "realtime" if landing.kind == "realtime" else ""}
        ctx = _models_context(catalog, rows, f, show_tokens=False, usage_raw=_q(request, "usage"))
        ctx["usage_hidden"] = []
        ctx["filtered"] = landing.kind != "hub"
        ctx["total_rows"], ctx["rows"] = len(rows), rows[:LANDING_ROWS]
        siblings = [p for p in views.landing_pages(catalog).values() if p.type == mtype and p.kind != "hub"]
        hub = views.find_landing(catalog, mtype)
        crumbs = [("Home", "/"), (views.TYPE_LABELS[mtype], hub.url)] + ([(landing.label, landing.url)] if slug else [])
        wildcard = 0
        if landing.kind == "language":
            wildcard = sum(1 for r in views.active_models(catalog)
                           if r.model.type == mtype and "*" in r.model.languages and not landing.matches(r))
        faq = views.landing_faq(catalog, landing, rows)
        ctx.update({
            "landing": landing, "copy": views.landing_copy(catalog, landing, rows), "crumbs": crumbs,
            "by_language": [p for p in siblings if p.kind == "language"],
            "by_feature": [p for p in siblings if p.kind in ("feature", "open", "realtime")],
            "other_types": [p for p in views.landing_pages(catalog).values() if p.kind == "hub" and p.type != mtype],
            "wildcard": wildcard, "filter_url": f"/models?{_qs(f, sort=None)}",
            "tasks": views.task_cards(catalog, mtype) if landing.kind == "hub" else [],
            "tiered": landing.kind == "open", "faq": faq,
            "jsonld": [_breadcrumb_ld(crumbs)] + ([_faq_ld(faq)] if faq else []),
        })
        return templates.TemplateResponse(request, "landing.html", ctx)
    return page


for _slug in views.SLUG_TYPES:
    router.add_api_route(f"/{_slug}", _landing_page(_slug), methods=["GET"], response_class=HTMLResponse)
    router.add_api_route(f"/{_slug}/{{slug}}", _landing_page(_slug), methods=["GET"], response_class=HTMLResponse)


# Short aliases people type and share (/tts, /stt/hindi, /s2s): a permanent redirect to the one canonical URL,
# never a second copy of the page, so links to either count for the same page.
SHORT_TYPE_ALIASES = {"tts": "text-to-speech", "stt": "speech-to-text", "sts": "speech-to-speech",
                      "s2s": "speech-to-speech", "asr": "speech-to-text"}


def _short_alias(target: str):
    async def redirect(request: Request, slug: str = ""):
        from fastapi.responses import RedirectResponse
        url = f"/{target}" + (f"/{quote(slug)}" if slug else "")
        if request.url.query:
            url += "?" + request.url.query
        return RedirectResponse(url, status_code=301)
    return redirect


for _alias, _target in SHORT_TYPE_ALIASES.items():
    router.add_api_route(f"/{_alias}", _short_alias(_target), methods=["GET"])
    router.add_api_route(f"/{_alias}/{{slug}}", _short_alias(_target), methods=["GET"])


def _faq_ld(faq: list[tuple[str, str]]) -> dict:
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in faq]}


def _breadcrumb_ld(crumbs: list[tuple[str, str]]) -> dict:
    site = settings.site_url.rstrip("/")
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": name, "item": site + path}
        for i, (name, path) in enumerate(crumbs, 1)]}


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
        rows = [r for r in rows if r.voice.preview_url or r.voice.previews]
    if f["q"]:
        needle = f["q"].lower()
        rows = [r for r in rows if needle in r.voice.name.lower() or needle in r.voice.id.lower()
                or needle in (r.voice.description or "").lower() or needle in (r.voice.accent or "")
                or any(needle in t.lower() for t in r.voice.use_cases + r.voice.tags)]
    def _sample_rank(r) -> int:   # stable sort: samples in the filtered language, other samples, none
        s = views.voice_sample(r.voice, f["language"])
        return 2 if s is None else (1 if s.matched is False else 0)
    rows = sorted(rows, key=_sample_rank)
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
        "n_live": sum(1 for pd in catalog.providers.values() if pd.provider.status == "active"),
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
        "usage": views.parse_usage(row.model.type, _q(request, "usage")) if row.model.type in views.USAGE else None,
        "today": date.today(),
        "api_path": f"/v1/providers/{provider_id}/models/{quote(row.model.id, safe='')}",
        "lang_links": {views.language_name(page.value): page.url for page in views.landing_pages(catalog).values()
                       if page.type == row.model.type and page.kind == "language"
                       and page.value in {views.base_language(lang) for lang in row.model.languages}},
        "feature_links": {page.value: page.url for page in views.landing_pages(catalog).values()
                          if page.type == row.model.type and page.kind == "feature"},
        "hub": views.find_landing(catalog, row.model.type),
        "jsonld": [_breadcrumb_ld([("Home", "/"), (pd.provider.name, f"/providers/{provider_id}"),
                                   (row.model.name, views.model_url(row))])],
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


@router.get("/compare/{pair}", response_class=HTMLResponse)
async def provider_vs_page(request: Request, pair: str, catalog: Catalog = Depends(get_catalog)):
    x, sep, y = pair.partition("-vs-")
    if not sep or (x, y) not in set(views.provider_pairs(catalog)) | {(b, a) for a, b in views.provider_pairs(catalog)}:
        raise HTTPException(404, "Comparison not found")
    canonical = views.provider_pair_slug(x, y)
    if pair != canonical:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(f"/compare/{canonical}", status_code=301)
    a, b = sorted((x, y))
    cmp = views.provider_comparison(catalog, a, b)
    names = {pid: catalog.providers[pid].provider.name for pid in (a, b)}
    crumbs = [("Home", "/"), (names[a], f"/providers/{a}"), (f"{names[a]} vs {names[b]}", f"/compare/{canonical}")]
    model_compare = {t: "/compare?" + "&".join(f"m={quote(views.model_key(cmp.sides[t][pid].models[0]), safe='/')}"
                                               for pid in (a, b)) for t in cmp.types}
    return templates.TemplateResponse(request, "provider_vs.html", {
        "cmp": cmp, "pa": catalog.providers[a].provider, "pb": catalog.providers[b].provider, "names": names,
        "model_compare": model_compare, "crumbs": crumbs, "jsonld": [_breadcrumb_ld(crumbs)],
        "other_a": [(views.provider_pair_slug(a, o), catalog.providers[o].provider.name)
                    for o in views.compare_partners(catalog, a) if o != b][:12],
        "other_b": [(views.provider_pair_slug(b, o), catalog.providers[o].provider.name)
                    for o in views.compare_partners(catalog, b) if o != a][:12],
    })


@router.get("/alternatives", response_class=HTMLResponse)
async def alternatives_index(request: Request, catalog: Catalog = Depends(get_catalog)):
    subjects = views.alternatives_subjects(catalog)
    rows = [(pid, catalog.providers[pid].provider) for pid in subjects]
    return templates.TemplateResponse(request, "alternatives_index.html", {
        "live": [(pid, p) for pid, p in rows if p.status == "active"],
        "retired": [(pid, p) for pid, p in rows if p.status != "active"],
    })


@router.get("/alternatives/{provider_id}", response_class=HTMLResponse)
async def alternatives_page(request: Request, provider_id: str, catalog: Catalog = Depends(get_catalog)):
    if provider_id not in views.alternatives_subjects(catalog):
        raise HTTPException(404, "Page not found")
    page = views.alternatives_page(catalog, provider_id)
    p = catalog.providers[provider_id].provider
    crumbs = [("Home", "/"), ("Alternatives", "/alternatives"), (f"{p.name} alternatives", f"/alternatives/{provider_id}")]
    return templates.TemplateResponse(request, "alternatives.html", {
        "page": page, "p": p, "crumbs": crumbs, "jsonld": [_breadcrumb_ld(crumbs)],
        "hubs": {t: views.find_landing(catalog, t) for t in page.types},
    })


CHANGES_PER_PAGE = 300
_CHANGE_PRIORITY = {"model_removed": 0, "shutdown_announced": 1, "provider_retired": 2, "model_deprecated": 3,
                    "price_changed": 4, "price_published": 5, "now_ga": 6, "model_added": 8}


@router.get("/changes", response_class=HTMLResponse)
async def changes_page(request: Request, catalog: Catalog = Depends(get_catalog)):
    feed = list(load_changes(settings.data_path))[:CHANGES_PER_PAGE]
    days: dict[str, dict] = {}
    for c in feed:
        d = days.setdefault(c.date, {"providers": [], "events": []})
        (d["providers"] if c.kind == "provider_added" else d["events"]).append(c)
    for d in days.values():                    # what a reader acts on first; additions last
        d["events"].sort(key=lambda c: _CHANGE_PRIORITY.get(c.kind, 9))
    return templates.TemplateResponse(request, "changes.html", {
        "days": days, "total": len(feed), "kinds": KIND_LABELS,
        "names": {pid: pd.provider.name for pid, pd in catalog.providers.items()},
        "live": {views.model_key(r) for r in catalog.models},
    })


@router.get("/changes.xml")
async def changes_atom(catalog: Catalog = Depends(get_catalog)):
    """Atom feed: one entry per change, except new providers, which are one entry per day."""
    site = settings.site_url.rstrip("/")
    names = {pid: pd.provider.name for pid, pd in catalog.providers.items()}
    entries: list[tuple[str, str, str, str, str, int]] = []     # id, date, title, link, summary, priority
    added: dict[str, list[str]] = {}
    for c in load_changes(settings.data_path):
        name = names.get(c.provider_id, c.provider_id)
        if c.kind == "provider_added":
            added.setdefault(c.date, []).append(name)
            continue
        what = f"{name} {c.model_name}" if c.model_id else name
        detail = f"{c.before} → {c.after}" if c.before and c.after else (c.after or "")
        title = f"{KIND_LABELS.get(c.kind, c.kind)}: {what}" + (f" ({detail})" if detail else "")
        link = f"{site}/models/{c.model_key}" if c.model_id else f"{site}/providers/{c.provider_id}"
        entries.append((f"{c.commit}/{c.kind}/{c.model_key or c.provider_id}", c.date, title, link, title,
                        _CHANGE_PRIORITY.get(c.kind, 9)))
    for day, provs in added.items():
        entries.append((f"providers/{day}", day, f"{len(provs)} provider{'s' if len(provs) != 1 else ''} added",
                        f"{site}/changes", "Added: " + ", ".join(sorted(provs)), 7))
    # newest day first; within a day the same order as /changes (shutdowns and prices before additions)
    entries.sort(key=lambda e: (-date.fromisoformat(e[1]).toordinal(), e[5]))
    entries = entries[:100]
    updated = (entries[0][1] if entries else date.today().isoformat()) + "T00:00:00Z"
    body = "".join(
        f"<entry><id>tag:voicedex.dev,2026:change/{escape(i)}</id><title>{escape(t)}</title>"
        f'<link href="{escape(link)}"/><updated>{d}T00:00:00Z</updated><summary>{escape(sm)}</summary></entry>'
        for i, d, t, link, sm, _ in entries)
    xml = ('<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom">'
           f"<title>{escape(settings.site_name)}: catalog changes</title>"
           f'<subtitle>New speech models, price changes, shutdown announcements and deprecations.</subtitle>'
           f'<link href="{site}/changes.xml" rel="self"/><link href="{site}/changes"/>'
           f"<id>{site}/changes</id><updated>{updated}</updated>"
           f"<author><name>{escape(settings.site_name)}</name></author>{body}</feed>")
    return Response(xml, media_type="application/atom+xml")


@router.get("/docs", response_class=HTMLResponse)
async def api_docs(request: Request):
    """Themed API reference (Scalar) over the app's own OpenAPI schema."""
    return templates.TemplateResponse(request, "docs.html", {})


@router.get("/catalog.csv", include_in_schema=False)
async def catalog_csv(catalog: Catalog = Depends(get_catalog)):
    """Every active model as one CSV (spreadsheets, notebooks). Lives outside /v1 so crawlers may fetch it."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(views.CSV_COLUMNS)
    w.writerows(views.catalog_csv_rows(catalog, settings.site_url.rstrip("/")))
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'inline; filename="voicedex-models.csv"',
                             "Cache-Control": "public, max-age=3600"})


_FAVICON = Path(__file__).parent / "static" / "favicon.ico"


@router.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Root favicon: browsers and Google's favicon crawler request this path directly."""
    return Response(_FAVICON.read_bytes(), media_type="image/x-icon",
                    headers={"Cache-Control": "public, max-age=86400"})


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots():
    site = settings.site_url.rstrip("/")
    return ("User-agent: *\n"
            "Disallow: /search\n"            # result pages for arbitrary queries
            "Disallow: /models?*\n"          # filtered/paged list views: canonical to /models, endless combinations
            "Disallow: /voices?*\n"          # (model pages are all in the sitemap; plain /models and /voices stay open)
            "Allow: /compare/\n"             # provider-vs-provider pages (curated, finite)
            "Disallow: /compare\n"           # unbounded combinations of models
            "Disallow: /v1/\n"               # the JSON API
            f"\nSitemap: {site}/sitemap.xml\n")


@router.get("/sitemap.xml")
async def sitemap(catalog: Catalog = Depends(get_catalog)):
    site = settings.site_url.rstrip("/")
    models = views.active_models(catalog)
    entries: list[tuple[str, date | None]] = [
        ("/", views.last_modified(models)), ("/models", views.last_modified(models)),
        ("/voices", views.last_modified(views.active_voices(catalog))), ("/docs", None),
    ]
    for pid in sorted(catalog.providers):
        pd = catalog.providers[pid]
        changed = views.last_modified(views.active_models(catalog, pid) + views.active_voices(catalog, pid))
        entries.append((f"/providers/{pid}", max(filter(None, (changed, pd.provider.last_synced)), default=None)))
    for x, y in views.provider_pairs(catalog):
        changed = views.last_modified(views.active_models(catalog, x) + views.active_models(catalog, y))
        entries.append((f"/compare/{views.provider_pair_slug(x, y)}", changed))
    feed = load_changes(settings.data_path)
    entries.append(("/changes", date.fromisoformat(feed[0].date) if feed else None))
    entries.append(("/alternatives", None))
    entries.append(("/coverage", views.last_modified(models)))
    entries.append(("/mcp", None))
    for pid in views.alternatives_subjects(catalog):
        entries.append((f"/alternatives/{pid}", views.last_modified(
            [r for r in views.active_models(catalog) if r.model.type in views._provider_types(catalog, pid)])))
    for path, page in sorted(views.landing_pages(catalog).items()):
        entries.append((path, views.last_modified(views.landing_rows(catalog, page))))
    entries += sorted((views.model_url(r), r.model.updated_at or r.model.first_seen) for r in models)
    body = "".join(f"<url><loc>{escape(site + p)}</loc>" + (f"<lastmod>{d.isoformat()}</lastmod>" if d else "")
                   + "</url>" for p, d in entries)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>'
    return Response(xml, media_type="application/xml")


LLMS_LANGUAGES = 20   # per model type: the languages with the most models


@router.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt(catalog: Catalog = Depends(get_catalog)):
    """https://llmstxt.org: a plain-Markdown map of the site for LLMs and AI search tools."""
    site = settings.site_url.rstrip("/")
    summaries = views.provider_summaries(catalog)
    live = [s for s in summaries if s.status == "active"]
    n_models, n_voices = len(views.active_models(catalog)), len(views.active_voices(catalog))
    hubs = [p for p in views.landing_pages(catalog).values() if p.kind == "hub"]
    lines = [
        f"# {settings.site_name}", "",
        f"> Open catalog of speech AI: {n_models} speech-to-text, text-to-speech and speech-to-speech models and "
        f"{n_voices:,} voices from {len(live)} providers, with supported languages, features, prices, regions and "
        "shutdown dates. Free, read-only JSON API; data is synced from provider APIs and docs and versioned in git.",
        "",
        "Prices are normalized for comparison: text-to-speech in USD per 1M characters, speech-to-text and "
        "speech-to-speech in USD per hour of audio. Non-USD prices are shown as published, never converted. "
        "Language codes are BCP-47; \"*\" means the provider supports many languages without listing them.",
        "", "## Data", "",
        f"- [Full catalog as JSON]({site}/v1/catalog.json): every provider, model and voice in one response",
        f"- [API reference]({site}/docs): REST endpoints with filters for type, language, feature, region and price",
        f"- [OpenAPI schema]({site}/openapi.json)",
        f"- [MCP server]({site}/mcp): Streamable HTTP endpoint for AI assistants (search, compare, price models and voices)",
        f"- [All models as CSV]({site}/catalog.csv): one row per model with normalized price, price source and check date",
        f"- [What changed]({site}/changes) ([Atom feed]({site}/changes.xml)): new models, price changes, shutdowns",
        "- [Source and data on GitHub](https://github.com/chandradot99/voicedex)",
        "", "## Compare models", "",
    ]
    lines += [f"- [{views.TYPE_LABELS[p.type]} models]({site}{p.url})" for p in hubs]
    lines += [f"- [All models, filterable]({site}/models)", f"- [Voices with audio samples]({site}/voices)",
              f"- [Alternatives to a provider]({site}/alternatives): who else offers the same, e.g. "
              f"[ElevenLabs alternatives]({site}/alternatives/elevenlabs)",
              f"- [Provider vs provider]({site}/compare/cartesia-vs-elevenlabs): side-by-side pages for "
              f"{len(views.provider_pairs(catalog))} pairs, e.g. Cartesia vs ElevenLabs",
              f"- [Language coverage]({site}/coverage): which providers support which languages"]
    pages = views.landing_pages(catalog)
    for mtype in views.TYPE_SLUGS:
        typed = [p for p in pages.values() if p.type == mtype and p.kind != "hub"]
        if not typed:
            continue
        label = views.TYPE_LABELS[mtype]
        lines += ["", f"## {label} by need", ""]
        lines += [f"- [{label}: {p.label}]({site}{p.url})"
                  for p in typed if p.kind in ("realtime", "open", "feature")]
        langs = sorted((p for p in typed if p.kind == "language"),
                       key=lambda p: -len(views.landing_rows(catalog, p)))[:LLMS_LANGUAGES]
        if langs:
            lines.append(f"- {label} by language: " + ", ".join(
                f"[{p.label}]({site}{p.url})" for p in sorted(langs, key=lambda p: p.label)))
    lines += ["", "## Providers", ""]

    def _n(n: int, word: str) -> str:
        return f"{n} {word}" + ("" if n == 1 else "s")
    lines += [f"- [{s.name}]({site}/providers/{s.id}): {_n(s.models, 'model')}"
              + (f", {_n(s.voices, 'voice')}" if s.voices else "") for s in sorted(live, key=lambda s: s.name.lower())]
    retired = [s for s in summaries if s.status != "active"]
    if retired:
        lines += ["", "## Optional", "", "Providers that shut down or stopped selling (kept for the record):", ""]
        lines += [f"- [{s.name}]({site}/providers/{s.id})" for s in retired]
    return "\n".join(lines) + "\n"


@router.get("/redoc")
async def redoc_redirect():
    from fastapi.responses import RedirectResponse
    return RedirectResponse("/docs", status_code=301)
