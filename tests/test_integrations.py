"""Framework integrations: schema rules, the apply script, and the filters on the site, API and MCP."""
import json
import shutil

import pytest

from tests.conftest import TEST_PROVIDER
from voicedex.catalog.files import read_provider_dir
from voicedex.catalog.schema import Provider


def test_schema_rules():
    ok = {"framework": "livekit", "types": ["tts", "stt", "tts"], "url": "u", "as_of": "2026-11-24"}
    p = Provider(id="x", name="X", type="tts", integrations=[{**ok, "framework": "vapi"}, ok])
    assert [i.framework for i in p.integrations] == ["livekit", "vapi"]       # fixed order
    assert p.integrations[0].types == ["stt", "tts"]                          # deduped, ordered
    for bad in ({**ok, "framework": "bogus"}, {**ok, "types": []}, {**ok, "types": ["asr"]}):
        with pytest.raises(ValueError):
            Provider(id="x", name="X", type="tts", integrations=[bad])
    with pytest.raises(ValueError, match="one integration entry per framework"):
        Provider(id="x", name="X", type="tts", integrations=[ok, ok])


def test_apply_script_limits_types_and_removes_dropped(tmp_path, fixture_catalog):
    from scripts.apply_integrations import apply
    from tests.conftest import build_fixture_catalog
    data = tmp_path / "data"
    build_fixture_catalog(data)
    src = tmp_path / "livekit.json"
    src.write_text(json.dumps({"framework": "livekit", "providers": {
        TEST_PROVIDER: {"types": ["tts", "sts"], "url": "https://docs.livekit.example/zz"}}}))
    from datetime import date
    assert apply(src, data, True, date(2026, 11, 24)) == 0
    got = {i.framework: i for i in read_provider_dir(data / TEST_PROVIDER).provider.integrations}
    assert got["livekit"].types == ["tts"]               # sts isn't a type we list for this provider
    assert "pipecat" in got                              # other frameworks untouched
    src.write_text(json.dumps({"framework": "livekit", "providers": {}}))
    assert apply(src, data, True, date(2026, 11, 25)) == 0
    assert "livekit" not in {i.framework for i in read_provider_dir(data / TEST_PROVIDER).provider.integrations}
    src.write_text(json.dumps({"framework": "livekit", "providers": {"nope": {"types": ["tts"], "url": "u"}}}))
    assert apply(src, data, True, date(2026, 11, 25)) == 1   # unknown provider id refuses
    shutil.rmtree(data)


async def test_api_framework_filters(client):
    models = (await client.get("/v1/models", params={"framework": "pipecat"})).json()["data"]
    assert sorted(m["model_id"] for m in models) == ["stt-eu", "stt-global"]    # STT only: the integration's type
    assert (await client.get("/v1/models", params={"framework": "vapi"})).json()["total"] == 0
    assert (await client.get("/v1/models", params={"framework": "bogus"})).status_code == 400
    provs = (await client.get("/v1/providers", params={"framework": "pipecat"})).json()
    assert [p["provider_id"] for p in provs] == [TEST_PROVIDER]
    assert provs[0]["integrations"][0]["framework"] == "pipecat"
    assert (await client.get("/v1/providers", params={"framework": "retell"})).json() == []


async def test_mcp_and_site(client, fixture_catalog, monkeypatch):
    from voicedex import mcp_server as m
    monkeypatch.setattr(m, "_cat", lambda: fixture_catalog)
    res = m.search_models(framework="pipecat")["results"]
    assert res and all(r["type"] == "stt" and r["works_with"] == ["pipecat"] for r in res)
    assert m.list_providers(framework="pipecat")["providers"][0]["integrations"][0]["types"] == ["stt"]
    assert m.list_providers(framework="vapi")["total"] == 0
    page = (await client.get("/models", params={"framework": "pipecat"})).text
    assert "2 matches" in page and "Works with" in page
    prov = (await client.get(f"/providers/{TEST_PROVIDER}")).text
    assert "https://docs.pipecat.example/zz" in prov
