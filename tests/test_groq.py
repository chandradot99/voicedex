"""Groq: audio models classified from the /models API (no hardcoded table)."""

from naaviq.sync.groq import parse_models

API = [
    {"id": "whisper-large-v3", "name": "Whisper", "owned_by": "OpenAI", "active": True,
     "input_modalities": ["audio"], "output_modalities": ["transcription"], "hugging_face_id": "openai/whisper-large-v3"},
    {"id": "canopylabs/orpheus-arabic-saudi", "name": "Canopy Labs Orpheus Arabic Saudi", "owned_by": "Canopy Labs",
     "active": True, "output_modalities": ["speech"], "context_window": 4000, "pricing": {"prompt": "0.00004"}},
    {"id": "openai/gpt-oss-20b", "output_modalities": ["text"], "active": True},
    {"id": "playai-tts", "output_modalities": ["speech"], "active": False},
]


def test_classification_from_modalities():
    stt, tts = parse_models(API)
    assert [m.model_id for m in stt] == ["whisper-large-v3"]
    assert [m.model_id for m in tts] == ["canopylabs/orpheus-arabic-saudi"]  # inactive + LLM skipped


def test_fields():
    stt, tts = parse_models(API)
    w, o = stt[0], tts[0]
    assert w.is_default and w.languages == ["*"] and w.meta["upstream"] == "OpenAI" and w.meta["batch"]
    assert o.languages == ["ar-SA"] and o.pricing["unit"] == "character" and o.pricing["price_usd"] == 0.00004
    assert o.max_text_chars == 4000 and not o.is_default  # preferred default not served → no phantom default
