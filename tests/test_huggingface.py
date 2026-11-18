"""Open-weights syncer: Hub API rows → models (bar, repackaging filter, licences)."""

from voicedex.sync.huggingface import HuggingFaceSyncer, commercial_use


class _Org(HuggingFaceSyncer):
    provider_id = "test-org"
    hf_authors = ["org"]


def _row(repo, tag="text-to-speech", downloads=50_000, likes=10, card=None, tags=None, gated=False):
    return {"id": repo, "pipeline_tag": tag, "downloads": downloads, "likes": likes,
            "cardData": card or {}, "tags": tags or [], "gated": gated, "createdAt": "2026-01-02T00:00:00Z"}


def test_model_fields_and_licence():
    m = _Org()._to_model(_row("org/Voice-1B", card={"license": "apache-2.0", "language": ["en", "zh", "multilingual"]}))
    assert m.model_id == "org/Voice-1B" and m.type == "tts" and m.display_name == "Voice-1B"
    assert m.languages == ["en", "zh"]
    assert m.open_weights == {"license": "apache-2.0", "url": "https://huggingface.co/org/Voice-1B",
                              "commercial_use": True}
    assert m.meta["released"] == "2026-01-02" and not m.streaming


def test_bar_and_repackaging_filtered():
    s = _Org()
    assert s._to_model(_row("org/tiny", downloads=10, likes=5)) is None
    assert s._to_model(_row("org/popular", downloads=10, likes=500)) is not None
    assert s._to_model(_row("org/Voice-1B-GGUF")) is None
    assert s._to_model(_row("org/enhancer", tag="audio-to-audio")) is None


def test_licence_from_tags_and_other():
    s = _Org()
    assert s._to_model(_row("org/a", tags=["license:cc-by-nc-4.0"])).open_weights["commercial_use"] is False
    m = s._to_model(_row("org/b", card={"license": "other", "license_name": "custom-research"}))
    assert m.open_weights["license"] == "custom-research" and m.open_weights["commercial_use"] is False
    assert s._to_model(_row("org/c")).open_weights == {
        "license": "unspecified", "url": "https://huggingface.co/org/c", "commercial_use": None}
    assert commercial_use("llama3.2") is None and commercial_use("MIT") is True
