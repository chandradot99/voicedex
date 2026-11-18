"""Aivis model search (recorded shape) → voices; uploader account fields and descriptions never stored."""

from voicedex.sync.aivis import parse_voices


def test_public_model_row():
    rows = [
        {"aivm_model_uuid": "a59cb814-0083-4369-8542-f51a29e72af7", "name": "まお", "visibility": "Public",
         "voice_timbre": "YouthfulFemale", "category": "OriginalCharacter",
         "description": "CV: someone https://x.example", "tags": [{"name": "女性"}],
         "user": {"handle": "ozchat", "name": "Oz Chat", "account_type": "Official"},
         "model_files": [{"license_type": "ACML 1.0", "model_architecture": "Style-Bert-VITS2 (JP-Extra)"}],
         "speakers": [{"supported_languages": ["ja"], "styles": [
             {"name": "ノーマル", "voice_samples": [{"audio_url": "https://assets.example/0.m4a"}]}]}]},
        {"aivm_model_uuid": "hidden", "name": "x", "visibility": "Private"},
    ]
    [v] = parse_voices(rows)
    assert v.voice_id == "a59cb814-0083-4369-8542-f51a29e72af7" and v.gender == "female" and v.age == "young"
    assert v.languages == ["ja"] and v.preview_url == "https://assets.example/0.m4a" and v.compatible_models == ["*"]
    assert v.description is None and "handle" not in v.meta and v.meta["official"] is True
    assert v.meta["license"] == "ACML 1.0" and v.meta["styles"] == ["ノーマル"]
