"""Gradium: only catalog voices are published; private-use dialect subtags become accent/meta."""

from naaviq.sync.gradium import parse_voices


def test_catalog_only_and_dialects():
    v = parse_voices([
        {"uid": "a1", "name": "Bastien", "gender": "Male", "age": "Middle-age", "locale": "fr-fr-x-southern",
         "is_catalog": True, "tags": [{"category": "emotion", "value": "Happy"},
                                      {"category": "use-case", "value": "Narration"},
                                      {"category": "texture", "value": "grainy"}]},
        {"uid": "b2", "name": "Everly", "gender": "Female", "locale": "en-gb", "is_catalog": True, "tags": []},
        {"uid": "mine", "name": "My clone", "locale": "en-us", "is_catalog": False, "tags": []},
    ])
    by = {x.voice_id: x for x in v}
    assert set(by) == {"a1", "b2"}                                   # user voice never published
    assert by["a1"].languages == ["fr-FR"] and by["a1"].accent == "southern"
    assert by["a1"].meta == {"dialect": "southern", "texture": ["grainy"]} and by["a1"].tags == ["happy"]
    assert by["a1"].age == "middle age" and by["a1"].use_cases == ["Narration"]
    assert by["b2"].accent == "british"
