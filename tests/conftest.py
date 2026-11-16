"""Shared fixtures. Tests run against the DB in DATABASE_URL (migrated by CI)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from naaviq.db import AsyncSessionLocal
from naaviq.main import app
from naaviq.models import Model, Provider, SyncRun, Voice

TEST_PROVIDER = "zz-test-provider"
DEPRECATED_PROVIDER = "zz-test-deprecated"
_TEST_IDS = [TEST_PROVIDER, DEPRECATED_PROVIDER]

OLD = datetime(2020, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _purge() -> None:
    async with AsyncSessionLocal() as s:
        for table in (SyncRun, Voice, Model):
            await s.execute(delete(table).where(table.provider_id.in_(_TEST_IDS)))
        await s.execute(delete(Provider).where(Provider.provider_id.in_(_TEST_IDS)))
        await s.commit()


@pytest.fixture(scope="session")
async def seeded():
    """Seed a small, known dataset under test-only provider IDs; removed afterwards."""
    await _purge()
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as s:
        s.add_all([
            Provider(provider_id=TEST_PROVIDER, display_name="ZZ Test", type="both"),
            Provider(provider_id=DEPRECATED_PROVIDER, display_name="ZZ Gone", type="tts", deprecated_at=now),
        ])
        await s.flush()
        s.add_all([
            Model(provider_id=TEST_PROVIDER, model_id="stt-global", display_name="STT Global", type="stt",
                  languages=["*"], is_default=True, capabilities=["word_timestamps", "speaker_diarization"],
                  regions=["global"]),
            Model(provider_id=TEST_PROVIDER, model_id="stt-eu", display_name="STT EU", type="stt",
                  languages=["de-DE"], lifecycle="beta", capabilities=["word_timestamps"], regions=["eu"]),
            Model(provider_id=TEST_PROVIDER, model_id="tts-main", display_name="TTS Main", type="tts",
                  languages=["en-US"], is_default=True, capabilities=["emotion", "ssml"], regions=[]),
            Model(provider_id=TEST_PROVIDER, model_id="tts-old", display_name="TTS Old", type="tts",
                  lifecycle="deprecated", deprecated_at=now),
            Model(provider_id=DEPRECATED_PROVIDER, model_id="ghost", display_name="Ghost", type="tts"),
            Voice(provider_id=TEST_PROVIDER, voice_id="v-any", display_name="Anywhere Voice", gender="female",
                  category="premade", languages=["*"], compatible_models=["*"], accent="british",
                  capabilities=["emotion"]),
            Voice(provider_id=TEST_PROVIDER, voice_id="v-hi", display_name="Hindi Voice", gender="male",
                  category="premade", languages=["hi-IN"], compatible_models=["tts-main"], accent="indian"),
            Voice(provider_id=TEST_PROVIDER, voice_id="v-unmapped", display_name="Unmapped Voice",
                  languages=[], compatible_models=[]),
            Voice(provider_id=TEST_PROVIDER, voice_id="v-gone", display_name="Gone Voice",
                  languages=["en-US"], compatible_models=["*"], deprecated_at=now),
            Voice(provider_id=DEPRECATED_PROVIDER, voice_id="ghost-v", display_name="Ghost Voice",
                  compatible_models=["*"]),
        ])
        await s.commit()
    yield {"seeded_at": now - timedelta(seconds=5)}
    await _purge()
