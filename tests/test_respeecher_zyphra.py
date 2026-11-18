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


def test_respeecher_marketplace_public_only():
    from voicedex.sync.respeecher import parse_marketplace_voices
    base = {"visibility": "public", "active": True, "available": True, "gender": "male", "age_group": "adult",
            "owner_id": "acct-1", "contact_url": "n/a", "category": "Voice Talent", "cost_multiplier": 1}
    rows = [
        {**base, "id": "v1", "name": "Adam S. Apple",
         "accents": [{"info": {"name": "Yours", "locale": "no_ac"}}, {"info": {"name": "American", "locale": "en_us"}}],
         "narration_styles": [{"tags": [{"name": "Neutral"}]}, {"tags": [{"name": "Excited"}]}]},
        {**base, "id": "v2", "name": "Private", "visibility": "private"},
        {**base, "id": "v3", "name": "Inactive", "active": False},
    ]
    [v] = parse_marketplace_voices(rows)
    assert v.voice_id == "v1" and v.languages == ["en-US"] and v.tags == ["neutral", "excited"]
    assert v.compatible_models == ["marketplace-sts", "marketplace-tts"]
    assert "owner_id" not in v.meta and "contact_url" not in v.meta and v.meta["accents"] == ["Yours", "American"]
