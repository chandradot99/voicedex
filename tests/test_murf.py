"""Murf voice mapping: non-BCP-47 locales, gender suffix in names, age in `description`."""

from naaviq.sync.murf import MurfAISyncer


def test_voice_mapping():
    v = MurfAISyncer()._parse_voices([
        {"voiceId": "en-SCOTT-rory", "displayName": "Rory (M)", "locale": "en-SCOTT", "gender": "Male",
         "description": "Middle-Aged", "availableStyles": ["Conversational"],
         "supportedLocales": {"en-SCOTT": {"detail": "English (Scottish)", "availableStyles": ["Narration"]},
                              "en-UK": {"detail": "English (UK)"}}},
    ])[0]
    assert v.display_name == "Rory" and v.gender == "male" and v.age == "middle aged"
    assert v.languages == ["en-GB"] and v.accent == "scottish"
    assert v.meta["styles"] == ["Conversational", "Narration"]
