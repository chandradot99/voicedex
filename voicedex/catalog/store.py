"""In-memory catalog loaded from data/ at startup (design D2)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from voicedex.catalog.files import DEFAULT_DATA_DIR, ProviderData, read_all
from voicedex.catalog.schema import Model, Provider, Voice

# Fixed namespace so public UUIDs are identical in every environment (design D6).
_NS = uuid.UUID("6f1c2a7e-3b0d-4c55-9a8e-1d2f3c4b5a69")


def model_uuid(provider_id: str, model: Model) -> uuid.UUID:
    return uuid.uuid5(_NS, f"model/{provider_id}/{model.type}/{model.id}")


def voice_uuid(provider_id: str, voice: Voice) -> uuid.UUID:
    return uuid.uuid5(_NS, f"voice/{provider_id}/{voice.id}")


def provider_uuid(provider_id: str) -> uuid.UUID:
    return uuid.uuid5(_NS, f"provider/{provider_id}")


@dataclass(frozen=True)
class ModelRow:
    provider_id: str
    model: Model


@dataclass(frozen=True)
class VoiceRow:
    provider_id: str
    voice: Voice


@dataclass
class Catalog:
    providers: dict[str, ProviderData] = field(default_factory=dict)
    models: list[ModelRow] = field(default_factory=list)
    voices: list[VoiceRow] = field(default_factory=list)
    etag: str = ""

    @classmethod
    def load(cls, data_dir: Path = DEFAULT_DATA_DIR) -> Catalog:
        providers = read_all(data_dir)
        models = [ModelRow(pid, m) for pid, pd in providers.items() for m in pd.models]
        voices = [VoiceRow(pid, v) for pid, pd in providers.items() for v in pd.voices]
        digest = hashlib.sha256()
        for pid, pd in providers.items():
            digest.update(json.dumps(pd.provider.model_dump(mode="json"), sort_keys=True).encode())
            for m in pd.models:
                digest.update(json.dumps(m.model_dump(mode="json"), sort_keys=True).encode())
            for v in pd.voices:
                digest.update(json.dumps(v.model_dump(mode="json"), sort_keys=True).encode())
        return cls(providers, models, voices, etag=f'"{digest.hexdigest()[:20]}"')

    def provider(self, provider_id: str) -> Provider | None:
        pd = self.providers.get(provider_id)
        return pd.provider if pd else None

    def active_provider_ids(self) -> set[str]:
        return {pid for pid, pd in self.providers.items() if pd.provider.status == "active"}


def language_matches(query: str, languages: list[str]) -> bool:
    """`en` matches en, en-US, en-GB…; `en-US` matches en-US and the bare `en`; `*` matches all."""
    q = query.strip()
    if not q:
        return True
    q_base = q.split("-")[0].lower()
    q_has_region = "-" in q
    for lang in languages:
        if lang == "*" or lang.lower() == q.lower():
            return True
        base = lang.split("-")[0].lower()
        if not q_has_region and base == q_base:
            return True
        if q_has_region and "-" not in lang and base == q_base:
            return True
    return False
