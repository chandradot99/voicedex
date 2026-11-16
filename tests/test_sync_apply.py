"""Tests for the diff/apply logic in scripts/sync.py (run against DATABASE_URL, rolled back)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from naaviq.db import AsyncSessionLocal
from naaviq.models import Model, Provider, Voice
from naaviq.sync.base import SyncModel, SyncVoice
from tests.conftest import TEST_PROVIDER

_spec = importlib.util.spec_from_file_location(
    "sync_script", Path(__file__).resolve().parents[1] / "scripts" / "sync.py"
)
sync_script = importlib.util.module_from_spec(_spec)
sys.modules["sync_script"] = sync_script  # dataclasses resolve types via sys.modules
_spec.loader.exec_module(sync_script)

PID = TEST_PROVIDER + "-apply"


@pytest.fixture
async def session():
    async with AsyncSessionLocal() as s:
        s.add(Provider(provider_id=PID, display_name="Apply Test", type="tts"))
        await s.flush()
        yield s
        await s.rollback()


async def _models(s, type_="tts") -> dict[str, Model]:
    rows = await s.execute(select(Model).where(Model.provider_id == PID, Model.type == type_))
    return {m.model_id: m for m in rows.scalars().all()}


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def test_apply_models_add_update_deprecate(session):
    stats = await sync_script._apply_models(PID, "tts", [
        SyncModel("a", "A", "tts", is_default=True),
        SyncModel("b", "B", "tts"),
    ], _now(), session)
    await session.flush()
    assert (stats.added, stats.updated, stats.deprecated) == (2, 0, 0)

    stats = await sync_script._apply_models(PID, "tts", [
        SyncModel("a", "A renamed", "tts", is_default=True, eol_date="2030-01-31"),
    ], _now(), session)
    await session.flush()
    assert (stats.added, stats.updated, stats.deprecated) == (0, 1, 1)

    models = await _models(session)
    assert models["a"].display_name == "A renamed"
    assert models["a"].eol_date.isoformat() == "2030-01-31"
    # Deprecation keeps lifecycle and deprecated_at in lockstep (DB CHECK)
    assert models["b"].deprecated_at is not None
    assert models["b"].lifecycle == "deprecated"


async def test_apply_models_undeprecates_on_reappearance(session):
    await sync_script._apply_models(PID, "tts", [SyncModel("a", "A", "tts")], _now(), session)
    await sync_script._apply_models(PID, "tts", [], _now(), session)
    await session.flush()
    await sync_script._apply_models(PID, "tts", [SyncModel("a", "A", "tts", lifecycle="beta")], _now(), session)
    await session.flush()
    m = (await _models(session))["a"]
    assert m.deprecated_at is None
    assert m.lifecycle == "beta"


async def test_apply_models_default_swap_respects_unique_index(session):
    await sync_script._apply_models(PID, "tts", [
        SyncModel("old", "Old", "tts", is_default=True),
        SyncModel("new", "New", "tts"),
    ], _now(), session)
    await session.flush()
    # Promote "new" and demote "old" in one sync — must not trip uq_models_one_default_per_provider_type
    await sync_script._apply_models(PID, "tts", [
        SyncModel("old", "Old", "tts"),
        SyncModel("new", "New", "tts", is_default=True),
    ], _now(), session)
    await session.flush()
    models = await _models(session)
    assert models["new"].is_default and not models["old"].is_default


async def test_apply_models_scoped_by_type(session):
    await sync_script._apply_models(PID, "stt", [SyncModel("s", "S", "stt")], _now(), session)
    stats = await sync_script._apply_models(PID, "tts", [SyncModel("t", "T", "tts")], _now(), session)
    await session.flush()
    assert stats.deprecated == 0
    assert (await _models(session, "stt"))["s"].deprecated_at is None


async def test_apply_voices_add_update_deprecate(session):
    await sync_script._apply_voices(PID, [
        SyncVoice("v1", "V1", accent="British", compatible_models=["*"]),
        SyncVoice("v2", "V2"),
    ], _now(), session)
    await session.flush()
    stats = await sync_script._apply_voices(PID, [SyncVoice("v1", "V1 new")], _now(), session)
    await session.flush()
    assert (stats.added, stats.updated, stats.deprecated) == (0, 1, 1)
    rows = await session.execute(select(Voice).where(Voice.provider_id == PID))
    voices = {v.voice_id: v for v in rows.scalars().all()}
    assert voices["v1"].display_name == "V1 new"
    assert voices["v2"].deprecated_at is not None


def test_redact_hides_password():
    out = sync_script._redact("postgresql+asyncpg://user:s3cret@host:5432/db")
    assert "s3cret" not in out
    assert "user" in out and "host" in out
