"""Munsit public voice catalogue (recorded shape) → voices; cloned voices never listed."""

from voicedex.sync.munsit import parse_voices


def test_catalogue_voice_and_clone_guard():
    rows = [
        {"voice_id": "PCtWbxjoNTpVQ6gIPaVZ2Hqm", "name": "Majed", "description": "Calm male voice",
         "gender": "male", "age": "middle", "languages": ["en", "ar"], "dialect": ["emirati"],
         "tags": ["educational"], "type": None, "sample_url": "https://signed.example/x.wav?X-Amz-Expires=3600",
         "is_cloned": False},
        {"voice_id": "cl-layla-8f21", "name": "Layla", "languages": ["ar"], "dialect": ["fusha"], "is_cloned": True},
    ]
    [v] = parse_voices(rows)
    assert v.voice_id == "PCtWbxjoNTpVQ6gIPaVZ2Hqm" and v.gender == "male" and v.accent == "emirati"
    assert v.languages == ["en", "ar-AE"] and v.use_cases == ["educational"]
    assert v.preview_url is None and v.meta == {"dialects": ["emirati"]}


def test_fusha_stays_plain_arabic():
    [v] = parse_voices([{"voice_id": "v1", "name": "A", "languages": ["ar"], "dialect": ["fusha"]}])
    assert v.languages == ["ar"]
