"""KugelAudio voice listing (recorded shape) → public voices only."""

from voicedex.sync.kugelaudio import parse_voices


def test_public_voice_kept_private_dropped():
    rows = [
        {"id": 2516, "voice_id": 2516, "handle": "2516", "public_id": "1f700520", "name": "Franziska Hörmann",
         "description": "Warm Allgäu accent.", "category": "conversational", "sex": "female", "age": "middle_age",
         "quality": "high", "supported_languages": ["de-DE"], "sample_url": "https://signed.example?X-Amz-Expires=900",
         "is_public": True, "verified": True},
        {"id": 9, "voice_id": 9, "name": "My clone", "supported_languages": ["en-GB"], "is_public": False},
    ]
    [v] = parse_voices(rows)
    assert v.voice_id == "2516" and v.gender == "female" and v.languages == ["de-DE"]
    assert v.use_cases == ["conversational"] and v.preview_url is None
    assert v.meta == {"quality": "high", "public_id": "1f700520"}
