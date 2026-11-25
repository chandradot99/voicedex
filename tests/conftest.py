"""Shared fixtures: a small, known catalog written to a temp data dir and served by the app."""

from __future__ import annotations

import os
from datetime import date

# Tests run against production behaviour, whatever a developer's .env says (load_dotenv never overrides).
os.environ["LOCAL_DEV"] = "false"

import pytest
from httpx import ASGITransport, AsyncClient

from voicedex.catalog.files import ProviderData, write_provider_dir
from voicedex.catalog.schema import Model, Provider, Voice
from voicedex.catalog.store import Catalog
from voicedex.main import app

TEST_PROVIDER = "zz-test-provider"
DEPRECATED_PROVIDER = "zz-test-deprecated"

OLD = date(2020, 1, 1)
NEW = date(2026, 11, 1)


def build_fixture_catalog(root) -> None:
    write_provider_dir(root / TEST_PROVIDER, ProviderData(
        Provider(id=TEST_PROVIDER, name="ZZ Test", type="both", last_synced=NEW,
                 integrations=[{"framework": "pipecat", "types": ["stt"], "url": "https://docs.pipecat.example/zz",
                                "as_of": NEW}]),
        models=[
            Model(id="stt-global", name="STT Global", type="stt", languages=["*"], is_default=True,
                  capabilities=["word_timestamps", "speaker_diarization"], regions=["global"], updated_at=OLD),
            Model(id="stt-eu", name="STT EU", type="stt", languages=["de-DE"], lifecycle="beta",
                  capabilities=["word_timestamps"], regions=["eu"], updated_at=OLD,
                  open_weights={"license": "apache-2.0", "commercial_use": True}),
            Model(id="tts-main", name="TTS Main", type="tts", languages=["en-US"], is_default=True,
                  capabilities=["emotion", "ssml"], updated_at=OLD,
                  pricing={"unit": "character", "price_usd": 0.00003},
                  latency={"ms": 75, "metric": "time_to_first_audio", "qualifier": "typical",
                           "conditions": "model inference only", "source_url": "https://zz.example/latency"},
                  benchmarks=[{"name": "tts_arena", "url": "https://arena.example/zz"}]),
            Model(id="tts-old", name="TTS Old", type="tts", lifecycle="deprecated",
                  deprecated_at=NEW, updated_at=NEW),
        ],
        voices=[
            Voice(id="v-any", name="Anywhere Voice", gender="female", category="premade", languages=["*"],
                  compatible_models=["*"], accent="British", capabilities=["emotion"], updated_at=OLD),
            Voice(id="v-hi", name="Hindi Voice", gender="male", category="premade", languages=["hi-IN"],
                  compatible_models=["tts-main"], accent="indian", tags=["warm"], updated_at=OLD),
            Voice(id="v-unmapped", name="Unmapped Voice", updated_at=OLD),
            Voice(id="v-gone", name="Gone Voice", languages=["en-US"], compatible_models=["*"],
                  deprecated_at=NEW, updated_at=NEW),
        ],
    ))
    write_provider_dir(root / DEPRECATED_PROVIDER, ProviderData(
        Provider(id=DEPRECATED_PROVIDER, name="ZZ Gone", type="tts", status="deprecated"),
        models=[Model(id="ghost", name="Ghost", type="tts")],
        voices=[Voice(id="ghost-v", name="Ghost Voice", compatible_models=["*"])],
    ))


@pytest.fixture(scope="session")
def fixture_catalog(tmp_path_factory) -> Catalog:
    root = tmp_path_factory.mktemp("data")
    build_fixture_catalog(root)
    return Catalog.load(root)


@pytest.fixture
async def client(fixture_catalog, monkeypatch):
    from voicedex.web import routes
    monkeypatch.setattr(routes, "load_changes", lambda _data_dir: ())   # never replay the real repo's git history
    app.state.catalog = fixture_catalog
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
