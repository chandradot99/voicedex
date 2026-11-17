"""Soniox: aliases folded into targets; docs removal dates → eol_date; shared voices only."""

from voicedex.sync.soniox import parse_removals, parse_stt_models, parse_tts_models, parse_voices

LANGS = [{"code": "en", "name": "English"}, {"code": "hi", "name": "Hindi"}]
STT = [
    {"id": "stt-rt-v6", "aliased_model_id": None, "name": "RT v6", "transcription_mode": "real_time",
     "languages": LANGS, "one_way_translation": "all_languages", "supports_agent_text_input": True},
    {"id": "stt-async-v6", "aliased_model_id": None, "transcription_mode": "async", "languages": LANGS},
    {"id": "stt-rt-v5", "aliased_model_id": None, "transcription_mode": "real_time", "languages": LANGS},
    {"id": "stt-rt-v4", "aliased_model_id": "stt-rt-v5", "transcription_mode": "real_time", "languages": LANGS},
]
DOCS = """| **stt-rt-v6** | Real-time | **Active** |
| **stt-rt-v5** | Real-time | **Deprecated**<br />Will be removed Dec 15, 2099 |
| **tts-rt-v1** | Real-time | **Deprecated**<br />Removed Aug 31, 2026 |"""


def test_removals_only_future_announcements():
    assert parse_removals(DOCS) == {"stt-rt-v5": "2099-12-15"}


def test_stt_models():
    m = {x.model_id: x for x in parse_stt_models(STT, parse_removals(DOCS))}
    assert set(m) == {"stt-rt-v6", "stt-async-v6", "stt-rt-v5"}            # alias not a record
    assert m["stt-rt-v6"].is_default and "translation" in m["stt-rt-v6"].capabilities
    assert m["stt-rt-v5"].eol_date == "2099-12-15" and m["stt-rt-v5"].meta["replacement"] == "stt-rt-v6"
    assert m["stt-rt-v5"].meta["aliases"] == ["stt-rt-v4"]
    assert m["stt-async-v6"].meta["batch"] and m["stt-async-v6"].interfaces == ["http"]


def test_tts_and_voices():
    tts = parse_tts_models([
        {"id": "tts-rt-v2", "aliased_model_id": None, "languages": LANGS, "supports_voice_cloning": True},
        {"id": "tts-rt-v1", "aliased_model_id": "tts-rt-v2"},
    ], {})
    assert [t.model_id for t in tts] == ["tts-rt-v2"] and tts[0].is_default
    v = parse_voices({"tts-rt-v2": [{"id": "Daniel", "gender": "male", "age": "middle_aged",
                                      "accent": "british", "use_case": ["social_media"], "style": ["calm"]}]},
                     {"tts-rt-v2": ["en", "hi"]})
    assert v[0].languages == ["en", "hi"] and v[0].age == "middle aged" and v[0].use_cases == ["social media"]
