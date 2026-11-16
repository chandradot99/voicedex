"""Typecast: stock voices only; languages from compatible models; emotion presets → capability."""

from naaviq.sync.base import SyncModel
from naaviq.sync.typecastai import TypecastAISyncer

MODELS = [SyncModel("ssfm-v31", "SSFM v3.1", "tts", languages=["en", "ko"]),
          SyncModel("ssfm-v21", "SSFM v2.1", "tts", languages=["en"])]


def test_voice_mapping():
    v = TypecastAISyncer()._parse_voices([
        {"voice_id": "tc_1", "voice_name": "Ozzie", "gender": "male", "age": "middle_age", "voice_type": "original",
         "use_cases": ["Game"], "models": [{"version": "ssfm-v31", "emotions": ["happy"]}, {"version": "ssfm-v99"}]},
        {"voice_id": "tc_2", "voice_name": "My clone", "voice_type": "custom", "models": [{"version": "ssfm-v31"}]},
    ], MODELS)
    assert [x.voice_id for x in v] == ["tc_1"]
    o = v[0]
    assert o.compatible_models == ["ssfm-v31"] and o.languages == ["en", "ko"]
    assert o.capabilities == ["emotion"] and o.age == "middle age" and o.use_cases == ["Game"]
