"""Inworld voice mapping: private voices never published; BCP-47 languageCode preferred."""

from naaviq.sync.inworld import InworldAISyncer


def test_voice_mapping_and_private_voices_skipped():
    items = [
        {"voiceId": "Aanya", "displayName": "Aanya", "langCode": "HI_IN", "languageCode": "hi-IN",
         "gender": "female", "ageGroup": "middle_aged", "tags": ["news"], "categories": ["enterprise"],
         "source": "SYSTEM", "localizations": [{"languageCode": "en-IN"}]},
        {"voiceId": "my-clone", "langCode": "EN_US", "source": "USER"},
        {"voiceId": "Old", "langCode": "EN_US", "source": "SYSTEM"},
    ]
    v = {x.voice_id: x for x in InworldAISyncer()._parse_voices(items)}
    assert "my-clone" not in v
    assert v["Aanya"].languages == ["hi-IN", "en-IN"]
    assert v["Aanya"].tags == ["news"] and v["Aanya"].use_cases == ["enterprise"]
    assert v["Old"].languages == ["en-US"]  # legacy langCode fallback
