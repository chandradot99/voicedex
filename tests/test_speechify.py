"""Speechify voice mapping: per-model `name` field and per-model locales."""

from naaviq.sync.base import SyncModel
from naaviq.sync.speechify import SpeechifySyncer

MODELS = [SyncModel("simba-3.5", "Simba 3.5", "tts"), SyncModel("simba-3.0", "Simba 3.0", "tts")]


def test_voice_models_and_locales():
    v = SpeechifySyncer()._parse_voices([{
        "id": "aadhya", "display_name": "Aadhya", "gender": "female", "locale": "te-IN", "type": "shared",
        "preview_audio": "https://x/p.mp3", "tags": ["calm"], "staff_pick_rank": 1,
        "models": [
            {"name": "simba-3.5", "languages": [{"locale": "te-IN"}, {"locale": "en-IN"}]},
            {"name": "simba-3.0", "languages": [{"locale": "te-IN"}]},
            {"name": "simba-experimental", "languages": [{"locale": "te-IN"}]},
        ],
    }], MODELS)[0]
    assert v.compatible_models == ["simba-3.0", "simba-3.5"]
    assert v.languages == ["te-IN", "en-IN"]
    assert v.meta["unlisted_models"] == ["simba-experimental"]
    assert v.tags == ["calm"]


def test_legacy_model_key_still_supported():
    v = SpeechifySyncer()._parse_voices([{"id": "x", "models": [{"model": "simba-3.0"}]}], MODELS)[0]
    assert v.compatible_models == ["simba-3.0"] and v.languages == []
