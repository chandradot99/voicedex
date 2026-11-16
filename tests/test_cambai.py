"""CAMB.ai: only library-owned voices are published; integer languages mapped to locales."""

from naaviq.sync.cambai import CambAISyncer

LANGS = {1: "en-US", 31: "de-DE"}


def test_library_only_and_language_mapping():
    voices, skipped = CambAISyncer()._parse_voices([
        {"id": 1, "voice_name": "Audrey", "gender": 2, "age": 27, "language": 31, "owner_id": 50358, "tags": ["narration"]},
        {"id": 2, "voice_name": "My Clone", "gender": 1, "language": 1, "owner_id": 999999},
        {"id": 3, "voice_name": "Unknown lang", "gender": 1, "language": 777, "owner_id": 74991},
    ], LANGS)
    v = {x.voice_id: x for x in voices}
    assert "2" not in v and skipped == {999999: 1}          # private clone never published, but reported
    assert v["1"].languages == ["de-DE"] and v["1"].gender == "female" and v["1"].use_cases == ["narration"]
    assert v["3"].languages == []                             # unmapped id → unknown, not "*"
