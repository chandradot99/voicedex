"""IBM Watson: discontinued previous-gen STT dropped; LSMs kept; voices grouped into tiers."""

from voicedex.sync.ibm import IBMSyncer

STT = [
    {"name": "en-US", "rate": 16000, "language": "en-US", "description": "Large US English model",
     "supported_features": {"custom_language_model": True, "low_latency": True, "speaker_labels": True}},
    {"name": "en-US_Multimedia", "rate": 16000, "language": "en-US",
     "supported_features": {"custom_language_model": True, "speaker_labels": True}},
    {"name": "es-LA_Telephony", "rate": 8000, "language": "es-LA", "supported_features": {}},
    {"name": "en-US_BroadbandModel", "rate": 16000, "language": "en-US", "supported_features": {}},
    {"name": "en-US_ShortForm_NarrowbandModel", "rate": 8000, "language": "en-US", "supported_features": {}},
]
VOICES = [
    {"name": "en-US_MichaelV3Voice", "language": "en-US", "gender": "male",
     "supported_features": {"custom_pronunciation": True}},
    {"name": "en-US_EmmaExpressive", "language": "en-US", "gender": "female", "supported_features": {}},
    {"name": "es-LA_SofiaNatural", "language": "es-LA", "gender": "female", "supported_features": {}},
    {"name": "en-US_MichaelV2Voice", "language": "en-US", "gender": "male", "supported_features": {}},
]


def test_stt_generations():
    m = {x.model_id: x for x in IBMSyncer()._parse_stt_models(STT)}
    assert set(m) == {"en-US", "en-US_Multimedia", "es-LA_Telephony"}
    assert m["en-US"].meta["beta_features"] == ["speaker_labels"] and m["en-US"].meta["parent_model_id"] == "ibm-large-speech"
    assert m["en-US_Multimedia"].is_default and "speaker_diarization" in m["en-US_Multimedia"].capabilities
    assert m["es-LA_Telephony"].languages == ["es-419"] and m["es-LA_Telephony"].sample_rates_hz == [8000]


def test_voice_tiers():
    s = IBMSyncer()
    voices = {v.voice_id: v for v in s._parse_voices(VOICES)}
    assert "en-US_MichaelV2Voice" not in voices                     # withdrawn alias
    assert voices["en-US_EmmaExpressive"].display_name == "Emma"
    assert voices["es-LA_SofiaNatural"].compatible_models == ["ibm-natural"]
    models = {m.model_id: m for m in s._derive_tts_models(VOICES)}
    assert [k for k, m in models.items() if m.is_default] == ["ibm-neural"]
    assert "style_control" in models["ibm-expressive"].capabilities
    assert "phoneme_input" in models["ibm-neural"].capabilities
