"""CoeFont Pro voice list (recorded shape) → voices; creator account fields never stored."""

from voicedex.sync.coefont import parse_voices


def test_pro_voice_row():
    rows = [
        {"coefontId": "87ca5e91-368f-4a24-aad7-731d2df2fc73", "name": "ナレーター", "lang": "ja", "public": True,
         "pro": True, "official": False, "plan": "ultra", "version": 2, "caption": "最高精度,プロ",
         "tags": ["女性", "ナレーション"], "userId": "secret-user", "screenName": "handle",
         "description": "follow me https://x.example"},
        {"coefontId": "private-1", "name": "mine", "lang": "ja", "public": False, "pro": True},
    ]
    [v] = parse_voices(rows)
    assert v.voice_id == "87ca5e91-368f-4a24-aad7-731d2df2fc73" and v.gender == "female"
    assert v.languages == ["ja"] and v.tags == ["ナレーション"] and v.compatible_models == ["*"]
    assert v.description is None
    assert "userId" not in v.meta and "screenName" not in v.meta and v.meta["plan"] == "ultra"
