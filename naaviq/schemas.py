"""Public API response schemas. Field names stay compatible with v1; v2 fields are additive."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone

from pydantic import BaseModel

from naaviq.catalog.schema import Model, Provider, Voice
from naaviq.catalog.store import model_uuid, provider_uuid, voice_uuid


def _dt(d: date | None) -> datetime | None:
    # v1 exposed timestamps; v2 tracks dates. Midnight UTC keeps the wire type a datetime.
    return datetime.combine(d, time.min, tzinfo=timezone.utc) if d else None


class ProviderOut(BaseModel):
    id: uuid.UUID
    provider_id: str
    display_name: str
    type: str
    status: str
    website: str | None
    description: str | None
    source: str | None
    regions: list[str]
    compliance: list[str]
    links: dict
    api_urls: list[str]
    docs_urls: list[str]
    model_count: int
    voice_count: int
    last_synced_at: datetime | None
    retired_on: date | None
    deprecated_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def build(cls, p: Provider, model_count: int, voice_count: int) -> ProviderOut:
        return cls(
            id=provider_uuid(p.id), provider_id=p.id, display_name=p.name, type=p.type, status=p.status,
            website=p.website, description=p.description, source=p.source,
            regions=list(p.regions), compliance=list(p.compliance),
            links=p.links.model_dump(exclude_none=True),
            api_urls=p.api_urls, docs_urls=p.docs_urls,
            model_count=model_count, voice_count=voice_count,
            last_synced_at=_dt(p.last_synced),
            retired_on=p.retired_on,
            deprecated_at=None if p.status == "active" else _dt(p.retired_on or p.last_synced),
            updated_at=_dt(p.last_synced),
        )


class ModelOut(BaseModel):
    id: uuid.UUID
    provider_id: str
    model_id: str
    display_name: str
    type: str
    description: str | None
    family: str | None
    alias_of: str | None
    snapshot_date: date | None
    lifecycle: str
    is_default: bool
    languages: list[str]
    streaming: bool
    batch: bool | None
    interfaces: list[str]
    sample_rates_hz: list[int]
    audio_formats: list[str]
    max_text_chars: int | None
    max_audio_seconds: int | None
    capabilities: list[str]
    regions: list[str]
    pricing: dict
    open_weights: dict | None
    eol_date: date | None
    meta: dict
    provenance: dict | None
    first_seen: date | None
    deprecated_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def build(cls, provider_id: str, m: Model) -> ModelOut:
        d = m.model_dump(mode="json")
        return cls(
            id=model_uuid(provider_id, m), provider_id=provider_id, model_id=m.id, display_name=m.name,
            type=m.type, description=m.description, family=m.family, alias_of=m.alias_of,
            snapshot_date=m.snapshot_date, lifecycle=m.lifecycle, is_default=m.is_default,
            languages=m.languages, streaming=m.streaming, batch=m.batch, interfaces=list(m.interfaces),
            sample_rates_hz=m.sample_rates_hz, audio_formats=m.audio_formats,
            max_text_chars=m.max_text_chars, max_audio_seconds=m.max_audio_seconds,
            capabilities=m.capabilities, regions=list(m.regions),
            pricing={k: v for k, v in (d["pricing"] or {}).items() if v not in (None, [])},
            open_weights=d["open_weights"], eol_date=m.eol_date, meta=m.meta,
            provenance=d["provenance"], first_seen=m.first_seen,
            deprecated_at=_dt(m.deprecated_at), updated_at=_dt(m.updated_at),
        )


class VoiceOut(BaseModel):
    id: uuid.UUID
    provider_id: str
    voice_id: str
    display_name: str
    gender: str | None
    category: str | None
    languages: list[str]
    description: str | None
    preview_url: str | None
    accent: str | None
    age: str | None
    use_cases: list[str]
    tags: list[str]
    compatible_models: list[str]
    capabilities: list[str]
    meta: dict
    first_seen: date | None
    deprecated_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def build(cls, provider_id: str, v: Voice) -> VoiceOut:
        return cls(
            id=voice_uuid(provider_id, v), provider_id=provider_id, voice_id=v.id, display_name=v.name,
            gender=v.gender, category=v.category, languages=v.languages, description=v.description,
            preview_url=v.preview_url, accent=v.accent, age=v.age, use_cases=v.use_cases, tags=v.tags,
            compatible_models=v.compatible_models, capabilities=v.capabilities, meta=v.meta,
            first_seen=v.first_seen, deprecated_at=_dt(v.deprecated_at), updated_at=_dt(v.updated_at),
        )


class PaginatedModels(BaseModel):
    total: int
    limit: int
    offset: int
    data: list[ModelOut]


class PaginatedVoices(BaseModel):
    total: int
    limit: int
    offset: int
    data: list[VoiceOut]
