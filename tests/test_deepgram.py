"""Deepgram /v1/models parsing — per-language entries, junk IDs, defaults."""

from voicedex.sync.deepgram import DeepgramSyncer


def _stt(canonical, lang, streaming, batch, arch="nova-3"):
    return {"canonical_name": canonical, "architecture": arch, "languages": [lang],
            "streaming": streaming, "batch": batch, "version": "2026-01-01.0"}


DATA = {
    "stt": [
        _stt("nova-3-general", "hi", streaming=True, batch=False),
        _stt("nova-3-general", "en-us", streaming=False, batch=True),
        _stt("nova-2-general", "en", streaming=False, batch=True, arch="nova-2"),
        _stt("general-dQw4w9WgXcQ", "fr", streaming=True, batch=True, arch="base"),
    ],
    "tts": [
        {"canonical_name": "aura-2-thalia-en", "architecture": "aura-2", "languages": ["en-us"],
         "metadata": {"tags": ["feminine"]}},
        {"canonical_name": "aura-asteria-en", "architecture": "aura", "languages": ["en"],
         "metadata": {"tags": ["feminine"]}},
    ],
}


def test_stt_flags_aggregate_across_language_entries():
    stt, _ = DeepgramSyncer()._parse_models(DATA)
    m = {x.model_id: x for x in stt}["nova-3-general"]
    assert m.streaming is True
    assert m.meta["batch"] is True
    assert m.languages == ["en-US", "hi"]


def test_placeholder_models_are_dropped():
    stt, _ = DeepgramSyncer()._parse_models(DATA)
    assert "general-dQw4w9WgXcQ" not in {x.model_id for x in stt}


def test_defaults_follow_preference_and_are_unique():
    stt, tts = DeepgramSyncer()._parse_models(DATA)
    assert [x.model_id for x in stt if x.is_default] == ["nova-3-general"]
    assert [x.model_id for x in tts if x.is_default] == ["aura-2"]


def test_no_default_when_preferred_models_absent():
    data = {"stt": [_stt("nova-2-meeting", "en", True, True, arch="nova-2")], "tts": []}
    stt, _ = DeepgramSyncer()._parse_models(data)
    assert not any(x.is_default for x in stt)
