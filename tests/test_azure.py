"""Azure: voice-name → model family, family models, STT base-model modes."""

from naaviq.sync.azure import _stt_models, _to_voice, _tts_models, voice_family

VOICES = [
    {"ShortName": "en-US-AvaNeural", "DisplayName": "Ava", "Gender": "Female", "Locale": "en-US",
     "Status": "GA", "VoiceType": "Neural", "SampleRateHertz": "24000", "StyleList": ["cheerful"],
     "VoiceTag": {"ModelSeries": ["Monolingual"], "PersonaId": ["Ava"]}},
    {"ShortName": "en-US-AvaMultilingualNeural", "DisplayName": "Ava Multilingual", "Gender": "Female",
     "Locale": "en-US", "SecondaryLocaleList": ["fr-FR"], "Status": "GA", "VoiceType": "Neural",
     "VoiceTag": {"Capabilities": ["multi-lingual"]}},
    {"ShortName": "en-US-Ava:DragonHDLatestNeural", "DisplayName": "Ava Dragon HD Latest", "Gender": "Female",
     "Locale": "en-US", "Status": "GA", "VoiceType": "NeuralHD", "VoiceTag": {"PersonaId": ["Ava"]}},
    {"ShortName": "cs-CZ-Grant:MAI-Voice-2.1-Flash", "DisplayName": "Grant MAI-Voice-2.1-Flash", "Gender": "Male",
     "Locale": "cs-CZ", "Status": "Preview", "VoiceType": "Neural", "VoiceTag": {"PersonaId": ["Grant"]}},
]


def test_voice_family_from_short_name():
    assert [voice_family(v["ShortName"]) for v in VOICES] == \
        ["Neural", "MultilingualNeural", "DragonHDLatestNeural", "MAI-Voice-2.1-Flash"]
    assert voice_family("en-US-AndrewTurboMultilingualNeural") == "TurboMultilingualNeural"


def test_family_models_default_and_lifecycle():
    models = {m.model_id: m for m in _tts_models(VOICES)}
    assert [m for m in models if models[m].is_default] == ["DragonHDLatestNeural"]
    assert models["MAI-Voice-2.1-Flash"].lifecycle == "beta"   # all its voices are Preview
    assert "style_control" in models["Neural"].capabilities and "ssml" in models["Neural"].capabilities


def test_voice_mapping():
    v = _to_voice(VOICES[1])
    assert (v.display_name, v.compatible_models, v.capabilities) == ("Ava", ["MultilingualNeural"], ["multilingual_native"])
    assert v.languages == ["en-US", "fr-FR"] and v.accent == "american"
    assert _to_voice(VOICES[3]).meta["status"] == "Preview"


def _base(locale, endpoints=True, transcriptions=True, name="", deprecates="2099-01-01T00:00:00Z"):
    return {"self": f"https://x/models/base/{locale}-{name or 'std'}", "locale": locale, "displayName": name,
            "properties": {"deprecationDates": {"transcriptionDateTime": deprecates},
                           "features": {"supportsEndpoints": endpoints, "supportsTranscriptions": transcriptions}}}


def test_stt_modes_from_live_base_models():
    models = {m.model_id: m for m in _stt_models([
        _base("en-US"), _base("fr-FR", endpoints=False), _base("de-DE", deprecates="2020-01-01T00:00:00Z"),
        _base("en-US", name="20240228 Whisper Large V2", deprecates="2027-04-15T00:00:00Z"),
    ])}
    assert models["azure-stt-realtime"].languages == ["en-US"]           # fr-FR batch-only; de-DE expired
    assert models["azure-stt-batch"].languages == ["en-US", "fr-FR"]
    assert models["whisper-large-v2"].eol_date == "2027-04-15"
