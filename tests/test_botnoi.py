"""Botnoi speaker lists (recorded shapes) → voices with generation-scoped ids."""

from voicedex.sync.botnoi import parse_v1_v2, parse_v4


def test_v1_v2_speakers():
    rows = [{"speaker_id": "2", "eng_name": "Bow", "thai_name": "โบว์", "eng_gender": "Female",
             "available_language": ["th", "en", "sg"], "eng_voice_style": ["Bright"], "audio": "https://x/a.mp3"},
            {"speaker_id": "", "eng_name": "skip"}]
    [v] = parse_v1_v2("v1", rows)
    assert v.voice_id == "v1-2" and v.display_name == "Bow" and v.gender == "female"
    assert v.languages == ["th", "en", "en-SG"] and v.compatible_models == ["v1"]
    assert v.meta["speaker_id"] == "2" and v.tags == ["bright"]


def test_v4_presets_only():
    payload = {"data": {"data": [
        {"voice_id": "a1", "name": "warm-narrator", "preset": True, "status": "ready"},
        {"voice_id": "c9", "name": "my-clone", "preset": False, "status": "ready"},
        {"voice_id": "p2", "name": "pending", "preset": True, "status": "processing"},
    ]}}
    [v] = parse_v4(payload)
    assert v.voice_id == "v4-a1" and v.display_name == "Warm Narrator" and v.compatible_models == ["v4"]
