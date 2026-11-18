"""
Catalog schema v2 — the single contract for data/ files, the API and exported JSON Schema.

See docs/design/v2-architecture.md. Controlled vocabularies are enums so invalid values fail at
write time (scripts/sync.py) and in CI (scripts/validate.py), not just at query time.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from voicedex.sync.language import normalize_languages

SCHEMA_VERSION = 2


# ── Controlled vocabularies ───────────────────────────────────────────────────

class ModelType(StrEnum):
    stt = "stt"
    tts = "tts"
    sts = "sts"   # speech-to-speech / realtime voice models


class Lifecycle(StrEnum):
    alpha = "alpha"
    beta = "beta"
    ga = "ga"
    deprecated = "deprecated"


class Region(StrEnum):
    us = "us"
    eu = "eu"
    asia = "asia"
    global_ = "global"


class Interface(StrEnum):
    http = "http"
    websocket = "websocket"
    grpc = "grpc"
    webrtc = "webrtc"


class Compliance(StrEnum):
    soc2 = "soc2"
    hipaa = "hipaa"
    gdpr = "gdpr"
    iso27001 = "iso27001"
    pci_dss = "pci_dss"


class Gender(StrEnum):
    male = "male"
    female = "female"
    neutral = "neutral"


class VoiceCategory(StrEnum):
    premade = "premade"
    cloned = "cloned"
    generated = "generated"


class Access(StrEnum):
    """How a developer gets access. Editorial (hand-set in provider.json)."""
    self_serve = "self_serve"      # sign up, get a key, pay per use or by credit
    enterprise = "enterprise"      # public API docs, but access or pricing goes through sales
    regional = "regional"          # needs a local ID, entity, phone or government registration
    open_weights = "open_weights"  # downloadable weights only; no first-party hosted API


class ProvenanceMethod(StrEnum):
    api = "api"
    docs = "docs"       # extracted from documentation (AI-assisted)
    manual = "manual"


STT_CAPABILITIES = frozenset({
    "word_timestamps", "speaker_diarization", "punctuation", "profanity_filter",
    "custom_vocabulary", "language_detection", "translation", "sentiment",
    "pii_redaction", "summarization", "topic_detection",
})
TTS_CAPABILITIES = frozenset({
    "emotion", "voice_cloning", "voice_design", "ssml", "phoneme_input",
    "prosody_control", "style_control", "multi_speaker",
})
MODEL_CAPABILITIES = STT_CAPABILITIES | TTS_CAPABILITIES
VOICE_CAPABILITIES = frozenset({"emotion", "multilingual_native"})

PRICING_UNITS = frozenset({"character", "byte", "minute", "second", "word", "token", "request", "hour"})


def _check_vocab(values: list[str], allowed: frozenset[str], what: str) -> list[str]:
    bad = sorted(set(values) - allowed)
    if bad:
        raise ValueError(f"unknown {what}: {bad}; allowed: {sorted(allowed)}")
    return sorted(set(values))


Slug = Annotated[str, Field(min_length=1, max_length=256)]


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


# ── Building blocks ───────────────────────────────────────────────────────────

class Provenance(_Record):
    method: ProvenanceMethod
    urls: list[str] = Field(default_factory=list)
    as_of: date


class OpenWeights(_Record):
    license: str
    url: str | None = None
    # Whether the weights' licence permits commercial use. None = not stated / unclear.
    commercial_use: bool | None = None


class PriceVariant(_Record):
    applies_to: str
    unit: str
    price_usd: float | None = Field(default=None, ge=0)   # USD rows
    price: float | None = Field(default=None, ge=0)       # non-USD rows (parent Pricing.currency)


class FreeQuota(_Record):
    amount: float = Field(ge=0)
    unit: str
    period: str | None = None


class Pricing(_Record):
    """List price as published. USD → `price_usd`. Other currencies → `price` + `currency` (ISO 4217),
    never converted (FX would be a guess); `price_usd` stays null for them."""
    unit: str
    price_usd: float | None = Field(default=None, ge=0)
    price: float | None = Field(default=None, ge=0)
    currency: str = "USD"
    free_quota: FreeQuota | None = None
    variants: list[PriceVariant] = Field(default_factory=list)
    as_of: date | None = None
    source_url: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _currency(self) -> Pricing:
        self.currency = self.currency.upper()
        if self.currency == "USD":
            if self.price_usd is None:
                self.price_usd = self.price
            self.price = None
            if self.price_usd is None:
                raise ValueError("USD pricing needs price_usd")
        elif self.price is None or self.price_usd is not None:
            raise ValueError(f"{self.currency} pricing needs `price` (and no price_usd)")
        return self

    @field_validator("unit")
    @classmethod
    def _unit(cls, v: str) -> str:
        if v not in PRICING_UNITS:
            raise ValueError(f"unknown pricing unit {v!r}; allowed: {sorted(PRICING_UNITS)}")
        return v


class ProviderLinks(_Record):
    docs: str | None = None
    api_reference: str | None = None
    pricing: str | None = None
    status: str | None = None


# ── Records ───────────────────────────────────────────────────────────────────

class Provider(_Record):
    id: Slug
    name: str
    type: ModelType | str  # "stt" | "tts" | "sts" | "both" — derived from active models by sync
    status: str = "active"  # "active" | "deprecated"
    website: str | None = None
    description: str | None = None
    access: Access | None = None         # editorial: self_serve | enterprise | regional | open_weights
    headquarters: str | None = None      # editorial: ISO 3166-1 alpha-2 country code, e.g. "IN"
    regions: list[Region] = Field(default_factory=list)
    compliance: list[Compliance] = Field(default_factory=list)
    links: ProviderLinks = Field(default_factory=ProviderLinks)
    # Where the data came from (sync-owned)
    source: ProvenanceMethod | str | None = None     # "api" | "docs" | "mixed"
    api_urls: list[str] = Field(default_factory=list)
    docs_urls: list[str] = Field(default_factory=list)
    voices_source: Provenance | None = None
    last_synced: date | None = None
    # Shut down / no longer sold to new customers. Set with status="deprecated"; the reason and the
    # source go in `description` / `links.status`. Kept in the catalog so "is X still alive?" is answerable.
    retired_on: date | None = None

    @field_validator("type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in {"stt", "tts", "sts", "both"}:
            raise ValueError(f"invalid provider type {v!r}")
        return v

    @field_validator("headquarters")
    @classmethod
    def _hq(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().upper()
        if len(v) != 2 or not v.isalpha():
            raise ValueError(f"headquarters must be an ISO 3166-1 alpha-2 code, got {v!r}")
        return v

    @field_validator("status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in {"active", "deprecated"}:
            raise ValueError(f"invalid provider status {v!r}")
        return v


class Model(_Record):
    id: Slug
    type: ModelType
    name: str
    description: str | None = None
    family: str | None = None          # family root id, e.g. "sonic-3"
    alias_of: str | None = None        # e.g. "sonic-latest" → "sonic-3"
    snapshot_date: date | None = None  # dated snapshots, e.g. sonic-3-2026-01-12
    lifecycle: Lifecycle = Lifecycle.ga
    is_default: bool = False
    languages: list[str] = Field(default_factory=list)
    streaming: bool = True
    batch: bool | None = None
    interfaces: list[Interface] = Field(default_factory=list)
    sample_rates_hz: list[int] = Field(default_factory=list)
    audio_formats: list[str] = Field(default_factory=list)
    max_text_chars: int | None = Field(default=None, ge=1)
    max_audio_seconds: int | None = Field(default=None, ge=1)
    capabilities: list[str] = Field(default_factory=list)
    regions: list[Region] = Field(default_factory=list)
    pricing: Pricing | None = None
    open_weights: OpenWeights | None = None
    eol_date: date | None = None
    meta: dict = Field(default_factory=dict)
    provenance: Provenance | None = None
    first_seen: date | None = None
    updated_at: date | None = None
    deprecated_at: date | None = None

    @field_validator("languages")
    @classmethod
    def _langs(cls, v: list[str]) -> list[str]:
        return normalize_languages(v)

    @field_validator("capabilities")
    @classmethod
    def _caps(cls, v: list[str], info) -> list[str]:
        return _check_vocab(v, MODEL_CAPABILITIES, "model capability")

    @field_validator("regions", "interfaces")
    @classmethod
    def _as_sorted_set(cls, v: list) -> list:
        # Set semantics: canonical order keeps diffs free of ordering noise.
        return sorted(set(v), key=str)

    @field_validator("audio_formats")
    @classmethod
    def _formats(cls, v: list[str]) -> list[str]:
        return sorted({f.strip().lower() for f in v if f.strip()})

    @field_validator("sample_rates_hz")
    @classmethod
    def _rates(cls, v: list[int]) -> list[int]:
        return sorted(set(v))

    def model_post_init(self, __context) -> None:
        if (self.lifecycle == Lifecycle.deprecated) != (self.deprecated_at is not None):
            raise ValueError(f"model {self.id}: lifecycle=deprecated and deprecated_at must be set together")


class VoicePreview(_Record):
    """A sample of the voice speaking one specific language."""
    language: str
    url: str

    @field_validator("language")
    @classmethod
    def _lang(cls, v: str) -> str:
        return normalize_languages([v])[0]


class Voice(_Record):
    id: Slug
    name: str
    gender: Gender | None = None
    age: str | None = None
    category: VoiceCategory | None = None
    description: str | None = None
    languages: list[str] = Field(default_factory=list)
    accent: str | None = None
    compatible_models: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    preview_url: str | None = None
    # Language spoken in `preview_url` (BCP-47), when the provider states it. None = not stated.
    preview_language: str | None = None
    # Further samples in other languages (providers that publish one per language), sorted by language.
    previews: list[VoicePreview] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)
    first_seen: date | None = None
    updated_at: date | None = None
    deprecated_at: date | None = None

    @field_validator("languages")
    @classmethod
    def _langs(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(normalize_languages(v)))

    @field_validator("compatible_models")
    @classmethod
    def _models_sorted(cls, v: list[str]) -> list[str]:
        return sorted(set(v))

    @field_validator("accent")
    @classmethod
    def _accent(cls, v: str | None) -> str | None:
        return (v.strip().lower() or None) if v else None

    @field_validator("preview_language")
    @classmethod
    def _preview_lang(cls, v: str | None) -> str | None:
        return normalize_languages([v])[0] if v else None

    @field_validator("previews")
    @classmethod
    def _previews(cls, v: list[VoicePreview]) -> list[VoicePreview]:
        return sorted(v, key=lambda p: p.language)

    @field_validator("capabilities")
    @classmethod
    def _caps(cls, v: list[str]) -> list[str]:
        return _check_vocab(v, VOICE_CAPABILITIES, "voice capability")
