"""Integration tests for public API filters (per-provider and cross-provider catalog)."""

from __future__ import annotations

from tests.conftest import DEPRECATED_PROVIDER, TEST_PROVIDER

MODELS = f"/v1/providers/{TEST_PROVIDER}/models"
VOICES = f"/v1/providers/{TEST_PROVIDER}/voices"


def _ids(resp, key: str) -> set[str]:
    assert resp.status_code == 200, resp.text
    return {row[key] for row in resp.json()["data"]}


# ── Providers ────────────────────────────────────────────────────────────────

async def test_list_providers_hides_deprecated(client):
    ids = {p["provider_id"] for p in (await client.get("/v1/providers")).json()}
    assert TEST_PROVIDER in ids
    assert DEPRECATED_PROVIDER not in ids


async def test_list_providers_include_deprecated(client):
    ids = {p["provider_id"] for p in (await client.get("/v1/providers?include_deprecated=true")).json()}
    assert DEPRECATED_PROVIDER in ids


async def test_get_provider_404_for_unknown_and_deprecated(client):
    assert (await client.get("/v1/providers/does-not-exist")).status_code == 404
    assert (await client.get(f"/v1/providers/{DEPRECATED_PROVIDER}")).status_code == 404
    assert (await client.get(f"/v1/providers/{DEPRECATED_PROVIDER}/models")).status_code == 404


# ── Models ───────────────────────────────────────────────────────────────────

async def test_models_exclude_deprecated_by_default(client):
    assert _ids(await client.get(MODELS), "model_id") == {"stt-global", "stt-eu", "tts-main"}


async def test_models_include_deprecated(client):
    assert "tts-old" in _ids(await client.get(MODELS, params={"include_deprecated": "true"}), "model_id")


async def test_models_type_filter(client):
    assert _ids(await client.get(MODELS, params={"type": "tts"}), "model_id") == {"tts-main"}


async def test_models_capabilities_match_all(client):
    r = await client.get(MODELS, params={"capabilities": "word_timestamps,speaker_diarization"})
    assert _ids(r, "model_id") == {"stt-global"}
    r = await client.get(MODELS, params={"capabilities": "word_timestamps"})
    assert _ids(r, "model_id") == {"stt-global", "stt-eu"}


async def test_models_invalid_capability_400(client):
    assert (await client.get(MODELS, params={"capabilities": "telepathy"})).status_code == 400


async def test_models_lifecycle_filter(client):
    assert _ids(await client.get(MODELS, params={"lifecycle": "beta"}), "model_id") == {"stt-eu"}
    assert (await client.get(MODELS, params={"lifecycle": "nope"})).status_code == 400


async def test_models_region_matches_global_wildcard_but_not_unknown(client):
    # eu → stt-eu (explicit) + stt-global (global wildcard); tts-main has [] (unknown) → excluded
    assert _ids(await client.get(MODELS, params={"region": "eu"}), "model_id") == {"stt-eu", "stt-global"}
    assert _ids(await client.get(MODELS, params={"region": "US"}), "model_id") == {"stt-global"}
    assert (await client.get(MODELS, params={"region": "mars"})).status_code == 400


async def test_models_updated_since_auto_includes_deprecated(client):
    since = "2026-10-01T00:00:00Z"
    ids = _ids(await client.get(MODELS, params={"updated_since": since}), "model_id")
    assert ids == {"tts-old"}  # only it changed after `since`, and deprecated rows auto-included
    ids = _ids(await client.get(MODELS, params={"updated_since": since, "include_deprecated": "false"}), "model_id")
    assert ids == set()
    ids = _ids(await client.get(MODELS, params={"updated_since": "2019-01-01"}), "model_id")
    assert ids == {"stt-global", "stt-eu", "tts-main", "tts-old"}


async def test_models_pagination(client):
    r = await client.get(MODELS, params={"limit": 1, "offset": 1})
    body = r.json()
    assert body["total"] == 3
    assert len(body["data"]) == 1


# ── Voices ───────────────────────────────────────────────────────────────────

async def test_voices_exclude_deprecated_by_default(client):
    assert _ids(await client.get(VOICES), "voice_id") == {"v-any", "v-hi", "v-unmapped"}


async def test_voices_language_wildcard(client):
    assert _ids(await client.get(VOICES, params={"language": "hi-IN"}), "voice_id") == {"v-any", "v-hi"}
    assert _ids(await client.get(VOICES, params={"language": "fr-FR"}), "voice_id") == {"v-any"}


async def test_voices_model_wildcard_and_unmapped(client):
    # [] (unmapped) must not match any model filter
    assert _ids(await client.get(VOICES, params={"model": "tts-main"}), "voice_id") == {"v-any", "v-hi"}
    assert _ids(await client.get(VOICES, params={"model": "other"}), "voice_id") == {"v-any"}


async def test_voices_accent_case_insensitive(client):
    assert _ids(await client.get(VOICES, params={"accent": "British"}), "voice_id") == {"v-any"}


async def test_voices_gender_search_capabilities(client):
    assert _ids(await client.get(VOICES, params={"gender": "male"}), "voice_id") == {"v-hi"}
    assert _ids(await client.get(VOICES, params={"search": "hindi"}), "voice_id") == {"v-hi"}
    assert _ids(await client.get(VOICES, params={"capabilities": "emotion"}), "voice_id") == {"v-any"}
    # "ssml" is a model capability, not a voice one
    assert (await client.get(VOICES, params={"capabilities": "ssml"})).status_code == 400


# ── Catalog (cross-provider) ─────────────────────────────────────────────────

async def test_catalog_models_hides_deprecated_providers(client):
    ids = _ids(await client.get("/v1/models", params={"limit": 500, "search": "Ghost"}), "model_id")
    assert "ghost" not in ids


async def test_catalog_models_provider_filter(client):
    r = await client.get("/v1/models", params={"provider": TEST_PROVIDER, "type": "stt", "region": "eu"})
    assert _ids(r, "model_id") == {"stt-global", "stt-eu"}


async def test_catalog_voices_provider_filter(client):
    r = await client.get("/v1/voices", params={"provider": TEST_PROVIDER, "language": "hi-IN"})
    assert _ids(r, "voice_id") == {"v-any", "v-hi"}
    r = await client.get("/v1/voices", params={"provider": DEPRECATED_PROVIDER})
    assert _ids(r, "voice_id") == set()


# ── v2 additions ─────────────────────────────────────────────────────────────

async def test_models_language_base_matching(client):
    # "de" matches de-DE; "*" models always match
    assert _ids(await client.get(MODELS, params={"language": "de"}), "model_id") == {"stt-eu", "stt-global"}
    assert _ids(await client.get(MODELS, params={"language": "en"}), "model_id") == {"stt-global", "tts-main"}


async def test_voices_language_base_matching(client):
    assert _ids(await client.get(VOICES, params={"language": "hi"}), "voice_id") == {"v-any", "v-hi"}


async def test_voice_search_matches_tags(client):
    assert _ids(await client.get(VOICES, params={"search": "warm"}), "voice_id") == {"v-hi"}


async def test_invalid_enum_params_400(client):
    assert (await client.get(MODELS, params={"type": "video"})).status_code == 400
    assert (await client.get(VOICES, params={"gender": "robot"})).status_code == 400


async def test_get_single_model_and_voice(client):
    r = await client.get(f"{MODELS}/tts-main")
    assert r.status_code == 200 and r.json()["pricing"]["unit"] == "character"
    assert (await client.get(f"{MODELS}/tts-old")).json()["lifecycle"] == "deprecated"
    assert (await client.get(f"{MODELS}/nope")).status_code == 404
    assert (await client.get(f"{VOICES}/v-hi")).json()["accent"] == "indian"
    assert (await client.get(f"{VOICES}/nope")).status_code == 404


async def test_ids_are_stable_uuids(client):
    a = (await client.get(f"{MODELS}/tts-main")).json()["id"]
    b = (await client.get(MODELS, params={"type": "tts"})).json()["data"][0]["id"]
    assert a == b and len(a) == 36


async def test_catalog_export_and_etag(client):
    r = await client.get("/v1/catalog.json")
    assert r.status_code == 200
    body = r.json()
    assert body["schema_version"] == 2
    ids = {p["provider_id"] for p in body["providers"]}
    assert {TEST_PROVIDER, DEPRECATED_PROVIDER} <= ids
    etag = r.headers["etag"]
    assert (await client.get("/v1/catalog.json", headers={"If-None-Match": etag})).status_code == 304
    assert (await client.get(MODELS, headers={"If-None-Match": etag})).status_code == 304


async def test_provider_counts(client):
    p = (await client.get(f"/v1/providers/{TEST_PROVIDER}")).json()
    assert p["model_count"] == 3 and p["voice_count"] == 3


async def test_retired_provider_shape(client):
    p = (await client.get("/v1/providers", params={"include_deprecated": "true"})).json()
    gone = next(x for x in p if x["provider_id"] == DEPRECATED_PROVIDER)
    assert gone["status"] == "deprecated" and "retired_on" in gone
