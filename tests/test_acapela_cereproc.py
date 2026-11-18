"""Keyless voice lists (recorded rows) → voices."""

from voicedex.sync.acapela import parse_voices as acapela_voices
from voicedex.sync.cereproc import parse_voices as cereproc_voices


def test_acapela_row():
    rows = [{"name": "Leila22k_HQ", "speaker": "Leila", "type": "standard-classic", "language": "Arabic",
             "gender": "1", "locale": "ara-sau", "quality": "Classic", "age": "Adult", "mood": "Neutral"}]
    [v] = acapela_voices(rows)
    assert v.voice_id == "Leila22k_HQ" and v.languages and v.languages[0].startswith("ar")


def test_cereproc_row():
    payload = {"voices": [{"accent": "NL", "accent_code": "nl", "country": "Netherlands", "country_iso": "NL",
                           "gender": "female", "language": "Dutch", "language_iso": "nl", "name": "Ada",
                           "region": "Netherlands", "sample_rate": 24000}]}
    vs = cereproc_voices(payload)
    assert vs and all(v.gender == "female" for v in vs)
    assert any(v.display_name.startswith("Ada") for v in vs)
    assert all(v.languages and v.languages[0].startswith("nl") for v in vs)
