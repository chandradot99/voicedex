"""Neuphonic voice mapping: gender + accent from tags, underscore language codes."""

from naaviq.sync.neuphonic import NeurophonicSyncer


def test_voice_mapping():
    v = NeurophonicSyncer()._parse_voices([
        {"voice_id": "a", "name": "Aditya", "tags": ["Male", "Indian Accent", "Narrator"], "lang_code": "en", "type": "Standard"},
        {"voice_id": "b", "name": "Noura", "tags": ["Female"], "lang_code": "ar_sa"},
    ])
    assert (v[0].gender, v[0].accent, v[0].tags) == ("male", "indian", ["Indian Accent", "Narrator"])
    assert v[1].languages == ["ar-SA"] and v[1].accent is None
