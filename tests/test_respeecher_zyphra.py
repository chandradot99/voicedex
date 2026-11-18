"""Respeecher Space and Zyphra default voice lists (recorded shapes) → voices."""

from voicedex.sync.respeecher import parse_space_voices
from voicedex.sync.zyphra import parse_voices as zyphra_voices


def test_respeecher_space_voice():
    rows = [{"id": "marta", "full_name": "Marta: Conversational", "accent": "American", "gender": "female",
             "is_best": True, "sampling_params": {"temperature": 0.4}}]
    [v] = parse_space_voices("en-rt", ["en"], rows)
    assert v.voice_id == "marta" and v.languages == ["en-US"] and v.compatible_models == ["en-rt"]
    assert v.tags == ["conversational"] and v.meta == {"recommended": True} and v.gender == "female"


def test_respeecher_non_english_model_language():
    [v] = parse_space_voices("de-rt", ["de"], [{"id": "andreas-casual", "full_name": "Andreas: casual"}])
    assert v.languages == ["de"] and v.gender is None


def test_zyphra_default_voice():
    rows = [{"voice_id": "bc1abb8a", "name": "savannah", "display_name": "Savannah", "description": None,
             "language": "en-US", "gender": "female", "dimension": None, "sample_rate_hz": 44100}]
    [v] = zyphra_voices(rows)
    assert v.voice_id == "bc1abb8a" and v.display_name == "Savannah" and v.languages == ["en-US"]
    assert v.accent == "american" and v.compatible_models == ["*"]
