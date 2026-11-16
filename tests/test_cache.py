"""The .sync-cache/ handshake must always win over the Anthropic API path."""

from __future__ import annotations

import pytest

pytest.importorskip("anthropic")

from naaviq.sync import ai_parser  # noqa: E402
from naaviq.sync.ai_parser import AIParserError, parse_models_from_docs, parse_voices_from_docs  # noqa: E402
from naaviq.sync.base import SyncModel, SyncVoice  # noqa: E402
from naaviq.sync.cache import write_models_cache, write_voices_cache  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_cache_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # cache dir is relative (.sync-cache/)


@pytest.fixture
def _api_must_not_be_called(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("Anthropic client must not be created when cache exists")
    monkeypatch.setattr(ai_parser, "_make_client", boom)


async def test_models_cache_wins_even_with_api_key(monkeypatch, _api_must_not_be_called):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-be-used")
    write_models_cache("acme", "tts", [SyncModel("m1", "M1", "tts", languages=["en-us"])])
    models, notes = await parse_models_from_docs(["https://x"], "acme", "tts", api_key="sk-explicit")
    assert [m.model_id for m in models] == ["m1"]
    assert models[0].languages == ["en-US"]  # normalized on read
    assert notes["source"] == "cache"


async def test_voices_cache_wins_even_with_api_key(monkeypatch, _api_must_not_be_called):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-should-not-be-used")
    write_voices_cache("acme", [SyncVoice("v1", "V1")])
    voices, notes = await parse_voices_from_docs(["https://x"], "acme")
    assert [v.voice_id for v in voices] == ["v1"]
    assert notes["source"] == "cache"


async def test_cache_miss_without_key_raises_with_instructions(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(AIParserError, match="no cache found"):
        await parse_models_from_docs(["https://x"], "acme", "stt")
