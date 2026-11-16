"""MiniMax voice mapping: language from voice_id prefix, accent + gender from MiniMax's descriptions."""

from naaviq.sync.minimax import MinimaxSyncer


def test_voice_mapping():
    v = {x.voice_id: x for x in MinimaxSyncer()._parse_voices([
        {"voice_id": "English_expressive_narrator", "voice_name": "Expressive Narrator",
         "description": ["An expressive adult male voice with a British accent."], "created_time": "2025-01-01"},
        {"voice_id": "Chinese (Mandarin)_HK_Flight_Attendant", "voice_name": "HK Flight Attendant",
         "description": ["A polite female voice."]},
        {"voice_id": "Robot_Armor", "voice_name": "Robot Armor", "description": []},
    ])}
    narrator = v["English_expressive_narrator"]
    assert (narrator.languages, narrator.accent, narrator.gender) == (["en"], "british", "male")
    assert v["Chinese (Mandarin)_HK_Flight_Attendant"].languages == ["zh"]
    assert v["Robot_Armor"].languages == []  # no prefix, no stated language → unknown, not guessed
