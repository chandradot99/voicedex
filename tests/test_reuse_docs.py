"""--reuse-docs: docs-sourced records in data/ → .sync-cache → merge must be a no-op."""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

from naaviq.catalog.files import read_provider_dir, write_provider_dir
from naaviq.catalog.merge import merge
from naaviq.sync.base import SyncModel, SyncResult
from naaviq.sync.cache import read_models_cache

_spec = importlib.util.spec_from_file_location("sync_script", Path(__file__).resolve().parents[1] / "scripts" / "sync.py")
sync_script = importlib.util.module_from_spec(_spec)
sys.modules["sync_script"] = sync_script
_spec.loader.exec_module(sync_script)


@pytest.fixture(autouse=True)
def _cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # .sync-cache is relative


def test_reuse_docs_round_trip_is_a_noop(tmp_path):
    rich = SyncModel(
        model_id="sonic-3-2026-01-12", display_name="Sonic 3 snap", type="tts", languages=["en", "fr"],
        capabilities=["emotion"], sample_rates_hz=[24000], audio_formats=["mp3"], interfaces=["websocket"],
        pricing={"unit": "character", "price_usd": 0.00001, "as_of": "2026-11-01"}, eol_date="2027-01-01",
        meta={"parent_model_id": "sonic-3", "snapshot_date": "2026-01-12", "batch": False, "x": 1},
        source="docs",
    )
    result = SyncResult(stt_models=[], tts_models=[rich], tts_voices=[], source="mixed",
                        docs_urls=["https://docs.example"])
    pd, _ = merge(None, result, provider_id="acme", display_name="Acme", seeded_type="tts", today=date(2026, 11, 1))
    data_dir = tmp_path / "data"
    write_provider_dir(data_dir / "acme", pd)

    assert sync_script.seed_cache_from_data("acme", data_dir) == ["tts models (1)"]
    cached = read_models_cache("acme", "tts")
    again = SyncResult(stt_models=[], tts_models=cached, tts_voices=[], source="mixed",
                       docs_urls=["https://docs.example"])
    _, report = merge(read_provider_dir(data_dir / "acme"), again, provider_id="acme", display_name="Acme",
                      seeded_type="tts", today=date(2026, 11, 16))
    assert not report.has_changes


def test_seed_never_overwrites_existing_cache(tmp_path):
    result = SyncResult(stt_models=[], tts_models=[SyncModel("m", "M", "tts", source="docs")], tts_voices=[],
                        source="docs")
    pd, _ = merge(None, result, provider_id="acme", display_name="Acme", seeded_type="tts", today=date(2026, 11, 1))
    write_provider_dir(tmp_path / "data" / "acme", pd)
    fresh = Path(".sync-cache/acme_tts_models.json")
    fresh.parent.mkdir()
    fresh.write_text("[]")
    assert sync_script.seed_cache_from_data("acme", tmp_path / "data") == []
    assert fresh.read_text() == "[]"
