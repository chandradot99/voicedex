"""ElevenLabs /v1/models + /v2/voices mapping."""

from voicedex.sync.elevenlabs import ElevenLabsSyncer

MODELS = [
    {"model_id": "eleven_v4", "name": "Eleven v4", "can_do_text_to_speech": True, "can_use_style": False,
     "maximum_text_length_per_request": 10000, "languages": [{"language_id": "en"}, {"language_id": "cmn"}],
     "model_rates": {"character_cost_multiplier": 1.0}},
    {"model_id": "eleven_alpha_x", "name": "Alpha", "can_do_text_to_speech": True, "requires_alpha_access": True},
    {"model_id": "eleven_multilingual_v2", "name": "Multilingual v2", "can_do_text_to_speech": True,
     "can_use_style": True},
    {"model_id": "eleven_multilingual_sts_v2", "name": "STS", "can_do_voice_conversion": True},
]

VOICE = {
    "voice_id": "abc", "name": "Roger - Laid-Back, Casual", "category": "premade",
    "labels": {"accent": "american", "gender": "male", "age": "middle_aged", "use_case": "conversational",
               "language": "en", "descriptive": "classy"},
    "verified_languages": [{"language": "en", "locale": "en-US"}, {"language": "zh", "locale": "cmn-CN"}],
    "high_quality_base_model_ids": ["eleven_multilingual_v1", "eleven_turbo_v2"],
}


def test_models_split_by_capability_and_default_is_first_ga():
    stt, tts, sts = ElevenLabsSyncer()._parse_models(MODELS)
    assert [m.model_id for m in tts] == ["eleven_v4", "eleven_alpha_x", "eleven_multilingual_v2"]
    assert [m.model_id for m in tts if m.is_default] == ["eleven_v4"]
    assert [m.lifecycle for m in tts] == ["ga", "alpha", "ga"]
    assert [m.model_id for m in sts] == ["eleven_multilingual_sts_v2"] and sts[0].is_default
    assert stt == []


def test_model_fields():
    _, tts, _ = ElevenLabsSyncer()._parse_models(MODELS)
    v4, _, ml2 = tts
    assert v4.max_text_chars == 10000
    assert v4.languages == ["en", "zh"]
    assert ml2.capabilities == ["style_control"] and v4.capabilities == []


def test_voice_mapping():
    v = ElevenLabsSyncer()._parse_voices([VOICE, dict(VOICE, voice_id="cloned", category="cloned")])[0]
    assert (v.display_name, v.meta["tagline"]) == ("Roger", "Laid-Back, Casual")
    assert v.languages == ["en-US", "zh-CN"]  # bare "en" dropped once en-US present; cmn → zh
    assert v.compatible_models == ["*"]
    assert v.age == "middle aged" and v.use_cases == ["conversational"]
