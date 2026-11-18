"""Remote MCP server at /mcp: tools against the fixture catalog, plus the HTTP transport."""

import json

from voicedex import mcp_server as m
from voicedex.web.changes import Change


async def test_tools_on_fixture_catalog(client, monkeypatch):           # `client` installs the fixture catalog
    keys = lambda r: [x["key"] for x in r["results"]]                  # noqa: E731
    explicit = m.search_models(type="stt", language="de")
    assert keys(explicit) == ["zz-test-provider/stt/stt-eu"]            # "*" models don't claim German
    assert set(keys(m.search_models(type="stt", language="de", include_unlisted_languages=True))) == {
        "zz-test-provider/stt/stt-eu", "zz-test-provider/stt/stt-global"}
    tts = m.search_models(type="tts", max_price_usd=40)
    assert keys(tts) == ["zz-test-provider/tts/tts-main"] and tts["results"][0]["price_usd_normalized"] == 30.0
    assert m.search_models(capability="teleport")["error"].startswith("unknown capability")
    assert m.search_models(limit=10_000)["returned"] <= m.MAX_LIMIT
    assert m.get_model("zz-test-provider", "tts", "tts-main")["record"]["id"] == "tts-main"
    assert "error" in m.get_model("zz-test-provider", "tts", "nope")
    cmp = m.compare_models(["zz-test-provider/tts/tts-main", "nope/tts/x"])
    assert cmp["missing"] == ["nope/tts/x"] and cmp["compare_url"].endswith("m=zz-test-provider/tts/tts-main")
    assert {p["id"] for p in m.list_providers()["providers"]} == {"zz-test-provider"}
    assert "zz-test-deprecated" in {p["id"] for p in m.list_providers(include_retired=True)["providers"]}
    assert m.search_voices(gender="male")["results"][0]["name"] == "Hindi Voice"
    monkeypatch.setattr(m, "load_changes", lambda _d: (
        Change(date="2026-11-20", kind="shutdown_announced", provider_id="zz-test-provider", model_type="stt",
               model_id="stt-eu", after="2027-01-31"),))
    ch = m.recent_changes(kind="shutdown_announced")
    assert ch["changes"][0]["model"] == "zz-test-provider/stt/stt-eu"
    assert m.recent_changes(kind="nonsense")["error"].startswith("unknown kind")


async def test_http_transport(client):
    page = await client.get("/mcp", headers={"accept": "text/html"})
    assert page.status_code == 200 and "claude mcp add --transport http voicedex https://voicedex.dev/mcp" in page.text
    assert "<code>search_models</code>" in page.text
    sse = await client.get("/mcp", headers={"accept": "text/event-stream"})
    assert sse.status_code == 405 and sse.headers["allow"] == "POST"
    hdrs = {"content-type": "application/json", "accept": "application/json, text/event-stream"}
    async with m.server.session_manager.run():                          # normally entered by the app lifespan
        listed = (await client.post("/mcp", headers=hdrs, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})).json()
        assert {t["name"] for t in listed["result"]["tools"]} == {f.__name__ for f in m.TOOLS}
        assert all(t["annotations"]["readOnlyHint"] for t in listed["result"]["tools"])
        call = (await client.post("/mcp", headers=hdrs, json={
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "search_models", "arguments": {"type": "tts"}}})).json()
        assert json.loads(call["result"]["content"][0]["text"])["results"][0]["key"] == "zz-test-provider/tts/tts-main"
    assert "/mcp</loc>" in (await client.get("/sitemap.xml")).text
