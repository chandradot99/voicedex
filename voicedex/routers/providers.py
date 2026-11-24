from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from voicedex.catalog.store import Catalog
from voicedex.config import settings
from voicedex.limiter import limiter
from voicedex.routers._filters import (
    OPEN_WEIGHTS_DESC,
    UPDATED_SINCE_DESC,
    effective_include_deprecated,
    filter_models,
    filter_voices,
    get_catalog,
    sort_models,
    sort_voices,
)
from voicedex.schemas import ModelOut, PaginatedModels, PaginatedVoices, ProviderOut, VoiceOut

router = APIRouter(prefix="/providers", tags=["Providers"])


def _provider_out(catalog: Catalog, provider_id: str) -> ProviderOut:
    pd = catalog.providers[provider_id]
    return ProviderOut.build(
        pd.provider,
        model_count=sum(1 for m in pd.models if m.deprecated_at is None),
        voice_count=sum(1 for v in pd.voices if v.deprecated_at is None),
    )


def _require_active(catalog: Catalog, provider_id: str) -> None:
    if provider_id not in catalog.active_provider_ids():
        raise HTTPException(404, f"Provider '{provider_id}' not found")


@router.get("", response_model=list[ProviderOut], summary="List providers", description="All active providers with model and voice counts. Retired providers (shut down or no longer selling) appear with `include_deprecated=true`, with `status: deprecated` and `retired_on`.")
@limiter.limit(settings.rate_limit)
async def list_providers(
    request: Request,
    provider_type: str | None = Query(None, alias="type", description="Filter by type: stt, tts, sts, both"),
    updated_since: datetime | None = Query(None, description=UPDATED_SINCE_DESC),
    include_deprecated: bool | None = Query(None, description="Include deprecated providers."),
    compliance: str | None = Query(None, description="Comma-separated: soc2, hipaa, gdpr, iso27001, pci_dss; providers must list ALL."),
    access: str | None = Query(None, description="self_serve, enterprise, regional, open_weights"),
    headquarters: str | None = Query(None, description="ISO 3166-1 alpha-2 country code, e.g. US, GB, IN"),
    catalog: Catalog = Depends(get_catalog),
):
    """List voice providers."""
    need = {c.strip().lower() for c in compliance.split(",") if c.strip()} if compliance else set()
    incl = effective_include_deprecated(include_deprecated, updated_since)
    out = []
    for pid, pd in catalog.providers.items():
        p = pd.provider
        if not incl and p.status != "active":
            continue
        if provider_type and p.type != provider_type:
            continue
        if updated_since and (p.last_synced is None or p.last_synced < updated_since.date()):
            continue
        if need and not need <= {str(getattr(c, "value", c)).lower() for c in (p.compliance or [])}:
            continue
        if access and str(getattr(p.access, "value", p.access) or "").lower() != access.strip().lower():
            continue
        if headquarters and (p.headquarters or "").upper() != headquarters.strip().upper():
            continue
        out.append(_provider_out(catalog, pid))
    return sorted(out, key=lambda p: (p.display_name.lower(), p.provider_id))


@router.get("/{provider_id}", response_model=ProviderOut, summary="Get a provider")
@limiter.limit(settings.rate_limit)
async def get_provider(request: Request, provider_id: str, catalog: Catalog = Depends(get_catalog)):
    """Get a single active provider by ID."""
    _require_active(catalog, provider_id)
    return _provider_out(catalog, provider_id)


@router.get("/{provider_id}/models", response_model=PaginatedModels, summary="List a provider's models", description="One provider's models with the same filters as `/v1/models`.")
@limiter.limit(settings.rate_limit)
async def list_models(
    request: Request,
    provider_id: str,
    model_type: str | None = Query(None, alias="type", description="Filter by type: stt, tts, sts"),
    language: str | None = Query(None, description="Language code. 'en' matches en-US/en-GB…; '*' models always match."),
    capabilities: str | None = Query(None, description="Comma-separated canonical capabilities; models must have ALL of them"),
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
    """List models for a provider. Deprecated models excluded by default."""
    _require_active(catalog, provider_id)
    rows = filter_models(
        catalog.models, provider=provider_id, model_type=model_type, language=language,
        capabilities=capabilities, lifecycle=lifecycle, region=region, search=search,
        updated_since=updated_since, include_deprecated=include_deprecated, open_weights=open_weights,
        realtime=realtime, recommended=recommended, shutting_down=shutting_down, max_price_usd=max_price_usd,
    )
    rows = sort_models(rows, cross_provider=False, sort=sort)
    page = rows[offset:offset + limit]
    return PaginatedModels(total=len(rows), limit=limit, offset=offset,
                           data=[ModelOut.build(r.provider_id, r.model) for r in page])


@router.get("/{provider_id}/models/{model_id}", response_model=ModelOut, summary="Get a model", description="One model, including deprecated ones. Pass `type` when the same id exists for more than one model type.")
@limiter.limit(settings.rate_limit)
async def get_model(
    request: Request,
    provider_id: str,
    model_id: str,
    model_type: str | None = Query(None, alias="type", description="Disambiguate when an id exists for several types"),
    catalog: Catalog = Depends(get_catalog),
):
    """Get one model (including deprecated ones)."""
    _require_active(catalog, provider_id)
    for m in catalog.providers[provider_id].models:
        if m.id == model_id and (model_type is None or m.type == model_type):
            return ModelOut.build(provider_id, m)
    raise HTTPException(404, f"Model '{model_id}' not found for provider '{provider_id}'")


@router.get("/{provider_id}/voices", response_model=PaginatedVoices, summary="List a provider's voices", description="One provider's stock voices with the same filters as `/v1/voices`.")
@limiter.limit(settings.rate_limit)
async def list_voices(
    request: Request,
    provider_id: str,
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
    """List TTS voices for a provider. Deprecated voices excluded by default."""
    _require_active(catalog, provider_id)
    rows = filter_voices(
        catalog.voices, provider=provider_id, gender=gender, category=category, language=language,
        model=model, accent=accent, capabilities=capabilities, search=search,
        updated_since=updated_since, include_deprecated=include_deprecated,
        use_case=use_case, age=age, has_sample=has_sample, multilingual=multilingual,
    )
    rows = sort_voices(rows, cross_provider=False)
    page = rows[offset:offset + limit]
    return PaginatedVoices(total=len(rows), limit=limit, offset=offset,
                           data=[VoiceOut.build(r.provider_id, r.voice) for r in page])


@router.get("/{provider_id}/voices/{voice_id}", response_model=VoiceOut, summary="Get a voice")
@limiter.limit(settings.rate_limit)
async def get_voice(request: Request, provider_id: str, voice_id: str, catalog: Catalog = Depends(get_catalog)):
    """Get one voice (including deprecated ones)."""
    _require_active(catalog, provider_id)
    for v in catalog.providers[provider_id].voices:
        if v.id == voice_id:
            return VoiceOut.build(provider_id, v)
    raise HTTPException(404, f"Voice '{voice_id}' not found for provider '{provider_id}'")
