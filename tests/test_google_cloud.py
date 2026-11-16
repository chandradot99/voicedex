"""Google Cloud: voice tier/persona mapping and STT Locations API enrichment."""

from naaviq.sync.base import SyncModel
from naaviq.sync.google_cloud import GoogleCloudSyncer, _enrich_stt_models, _location_region


def test_voice_tiers_and_gemini_personas():
    items = [
        {"name": "en-US-Chirp3-HD-Kore", "languageCodes": ["en-US"], "ssmlGender": "FEMALE"},
        {"name": "en-US-Wavenet-A", "languageCodes": ["en-US"], "ssmlGender": "MALE"},
        {"name": "Kore", "languageCodes": ["en-US"], "ssmlGender": "FEMALE"},
    ]
    v = {x.voice_id: x for x in GoogleCloudSyncer()._parse_voices(items, ["gemini-2.5-flash-tts"])}
    assert (v["en-US-Chirp3-HD-Kore"].display_name, v["en-US-Chirp3-HD-Kore"].compatible_models) == ("Kore", ["Chirp3-HD"])
    assert v["en-US-Wavenet-A"].display_name == "Wavenet A"
    assert v["Kore"].compatible_models == ["gemini-2.5-flash-tts"]
    # Without Gemini models the bare personas are skipped rather than orphaned
    assert "Kore" not in {x.voice_id for x in GoogleCloudSyncer()._parse_voices(items, [])}


def test_location_region_mapping():
    assert [_location_region(x) for x in ("global", "us", "us-central1", "northamerica-northeast1",
                                           "eu", "europe-west4", "asia-south1", "australia-southeast1",
                                           "me-central1")] == \
        ["global", "us", "us", "us", "eu", "eu", "asia", "asia", None]


def test_enrich_api_authoritative_docs_kept():
    docs = [SyncModel("chirp_3", "Chirp 3", "stt", languages=["en-US"], capabilities=["translation"],
                      pricing={"unit": "minute", "price_usd": 0.016}, is_default=True, source="docs")]
    api = {
        "chirp_3": {"languages": {"en-US", "hi-IN", "auto"}, "locations": {"us", "asia-south1"},
                    "features": {"recognizer", "word_timestamps", "automatic_punctuation", "denoiser"},
                    "states": {"GA"}},
        "video": {"languages": {"en-US"}, "locations": {"global"}, "features": {"recognizer"},
                  "states": {"PUBLIC_PREVIEW"}},
    }
    out = {m.model_id: m for m in _enrich_stt_models(docs, api)}
    c3 = out["chirp_3"]
    assert c3.languages == ["en-US", "hi-IN"]            # "auto" is not a locale…
    assert "language_detection" in c3.capabilities        # …it's a capability
    assert {"translation", "word_timestamps", "punctuation"} <= set(c3.capabilities)  # docs-only cap kept
    assert c3.regions == ["asia", "us"] and c3.pricing["price_usd"] == 0.016 and c3.is_default
    assert c3.meta["features"] == ["denoiser"]
    video = out["video"]
    assert (video.source, video.lifecycle, video.regions) == ("api", "beta", ["global"])
