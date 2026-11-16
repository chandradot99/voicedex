"""Smallest AI: voices per model endpoint → real compatible_models; language names via shared map."""

from naaviq.sync.language import language_from_name
from naaviq.sync.smallestai import SmallestAISyncer, _slug


def test_slug():
    assert _slug("lightning_v3.1_pro") == "lightning-v3.1-pro"


def test_voices_union_across_model_endpoints():
    ben = {"voiceId": "ben", "displayName": "Ben", "tags": {"gender": "male", "accent": "german", "age": "young",
           "language": ["english", "norwegian"], "recommendedLanguages": ["german"], "usecases": ["Narration"]}}
    by_slug = {"lightning-v3.1-pro": [ben], "lightning-v3.1": [ben, {"voiceId": "old", "tags": {}}]}
    v = {x.voice_id: x for x in SmallestAISyncer()._parse_voices(by_slug, ["lightning_v3.1_pro", "lightning_v3.1"])}
    assert v["ben"].compatible_models == ["lightning_v3.1", "lightning_v3.1_pro"]
    assert v["ben"].languages == ["de", "en", "no"] or v["ben"].languages == ["de", "en", "no"][:]
    assert v["old"].compatible_models == ["lightning_v3.1"] and v["old"].languages == []


def test_language_from_name_never_guesses():
    assert (language_from_name("Norwegian"), language_from_name("Odia"), language_from_name("Klingon")) == ("no", "or", None)
