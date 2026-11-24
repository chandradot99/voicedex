"""Cross-provider endpoints — search models and voices across all providers, plus a full export."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request

from voicedex.catalog.schema import SCHEMA_VERSION
from voicedex.catalog.store import Catalog
from voicedex.config import settings
from voicedex.limiter import limiter
from voicedex.routers._filters import (
    OPEN_WEIGHTS_DESC,
    UPDATED_SINCE_DESC,
    filter_models,
    filter_voices,
    get_catalog,
    sort_models,
    sort_voices,
)
from voicedex.schemas import ModelOut, PaginatedModels, PaginatedVoices, ProviderOut, VoiceOut

router = APIRouter()


@router.get("/models", response_model=PaginatedModels, tags=["Models & voices"], summary="Search models across providers", description="Every speech-to-text, text-to-speech and speech-to-speech model in the catalog, filterable across providers. Deprecated models are hidden unless `include_deprecated=true` or `updated_since` is set.")
@limiter.limit(settings.rate_limit)
async def list_all_models(
    request: Request,
    provider: str | None = Query(None, description="Filter by provider ID e.g. deepgram, elevenlabs"),
    model_type: str | None = Query(None, alias="type", description="stt, tts, sts"),
    language: str | None = Query(None, description="Language code. 'en' matches en-US/en-GB…; '*' models always match."),
    capabilities: str | None = Query(None, description="Comma-separated canonical capabilities; models must have ALL"),
    lifecycle: str | None = Query(None, description="Comma-separated: alpha, beta, ga, deprecated"),
    region: str | None = Query(None, description="us, eu, asia, global. Matches the region OR 'global'."),
    search: str | None = Query(None, description="Case-insensitive match on name, id, description"),
    updated_since: datetime | None = Query(None, description=UPDATED_SINCE_DESC),
    include_deprecated: bool | None = Query(None, description="Include deprecated models."),
    open_weights: bool | None = Query(None, description=OPEN_WEIGHTS_DESC),
    realtime: bool | None = Query(None, description="true: models served over WebSocket or WebRTC (live voice agents, realtime transcription)."),
    recommended: bool | None = Query(None, description="true: models the provider's docs point new integrations to."),
    shutting_down: bool | None = Query(None, description="true: only models with an announced shutdown date (eol_date)."),
    max_price_usd: float | None = Query(None, ge=0, description="Upper bound on the normalized USD price (TTS per 1M characters, STT/STS per hour). Excludes models without a comparable USD price."),
    sort: str | None = Query(None, description="name (default), price (cheapest normalized USD first), newest (latest release first)."),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    catalog: Catalog = Depends(get_catalog),
):
    """List models across all active providers."""
    active = catalog.active_provider_ids()
    rows = filter_models(
        (r for r in catalog.models if r.provider_id in active),
        provider=provider, model_type=model_type, language=language, capabilities=capabilities,
        lifecycle=lifecycle, region=region, search=search,
        updated_since=updated_since, include_deprecated=include_deprecated, open_weights=open_weights,
        realtime=realtime, recommended=recommended, shutting_down=shutting_down, max_price_usd=max_price_usd,
    )
    rows = sort_models(rows, cross_provider=True, sort=sort)
    page = rows[offset:offset + limit]
    return PaginatedModels(total=len(rows), limit=limit, offset=offset,
                           data=[ModelOut.build(r.provider_id, r.model) for r in page])


@router.get("/voices", response_model=PaginatedVoices, tags=["Models & voices"], summary="Search voices across providers", description="Stock text-to-speech voices from every provider. Filter by language, gender, accent or the model a voice works with. Private or cloned voices are never included.")
@limiter.limit(settings.rate_limit)
async def list_all_voices(
    request: Request,
    provider: str | None = Query(None, description="Filter by provider ID"),
    gender: str | None = Query(None, description="male, female, neutral"),
    category: str | None = Query(None, description="premade, cloned, generated"),
    language: str | None = Query(None, description="Language code. 'en' matches en-US/en-GB…"),
    model: str | None = Query(None, description="Compatible TTS model id; voices listing it or '*' match"),
    accent: str | None = Query(None, description="e.g. british, american, indian (case-insensitive)"),
    capabilities: str | None = Query(None, description="Comma-separated voice capabilities; must have ALL"),
    search: str | None = Query(None, description="Case-insensitive match on name, id, tags, description"),
    updated_since: datetime | None = Query(None, description=UPDATED_SINCE_DESC),
    include_deprecated: bool | None = Query(None, description="Include deprecated voices."),
    use_case: str | None = Query(None, description="Conversational, Narration, Audiobooks & stories, Characters & gaming, Customer service, Ads & social, Education, Podcasts, News, Meditation (normalized from providers' use cases and tags)."),
    age: str | None = Query(None, description="Young, Adult, Middle-aged, Older, Teen, Child (normalized from providers' age labels)."),
    has_sample: bool | None = Query(None, description="true: only voices with an audio preview."),
    multilingual: bool | None = Query(None, description="true: voices that speak several languages."),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    catalog: Catalog = Depends(get_catalog),
):
    """List voices across all active providers."""
    active = catalog.active_provider_ids()
    rows = filter_voices(
        (r for r in catalog.voices if r.provider_id in active),
        provider=provider, gender=gender, category=category, language=language, model=model,
        accent=accent, capabilities=capabilities, search=search,
        updated_since=updated_since, include_deprecated=include_deprecated,
        use_case=use_case, age=age, has_sample=has_sample, multilingual=multilingual,
    )
    rows = sort_voices(rows, cross_provider=True)
    page = rows[offset:offset + limit]
    return PaginatedVoices(total=len(rows), limit=limit, offset=offset,
                           data=[VoiceOut.build(r.provider_id, r.voice) for r in page])


@router.get("/catalog.json", tags=["Bulk export"], summary="Download the whole catalog")
@limiter.limit(settings.rate_limit)
async def export_catalog(request: Request, catalog: Catalog = Depends(get_catalog)):
    """The entire catalog (every provider, model and voice, deprecated included) in one response.

    Cacheable: send `If-None-Match` with the previous ETag to get a 304 when nothing changed.
    """
    providers = []
    for pid, pd in sorted(catalog.providers.items()):
        p = ProviderOut.build(
            pd.provider,
            model_count=sum(1 for m in pd.models if m.deprecated_at is None),
            voice_count=sum(1 for v in pd.voices if v.deprecated_at is None),
        ).model_dump(mode="json")
        p["models"] = [ModelOut.build(pid, m).model_dump(mode="json") for m in pd.models]
        p["voices"] = [VoiceOut.build(pid, v).model_dump(mode="json") for v in pd.voices]
        providers.append(p)
    return {"schema_version": SCHEMA_VERSION, "etag": catalog.etag.strip('"'), "providers": providers}
