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
    assert m.get_model("zz-test-provider/tts/tts-main")["record"]["id"] == "tts-main"
    assert "error" in m.get_model("zz-test-provider/tts/nope-nothing-like-it")
    cmp = m.compare_models(["zz-test-provider/tts/tts-main", "nope/tts/x"])
    assert cmp["missing"][0]["query"] == "nope/tts/x" and cmp["compare_url"].endswith("m=zz-test-provider/tts/tts-main")
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
    assert page.headers["cache-control"] == sse.headers["cache-control"] == "no-store"   # CDN must not cache /mcp
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


async def test_v2_tools(client):
    # loose names always resolve to the best match and say so; nonsense gets no random suggestions
    loose = m.compare_models(["ZZ Test TTS Main", "zz-test-provider stt", "zz test tts mian", "nonexistent foo"])
    assert [x["key"] for x in loose["models"]] == ["zz-test-provider/tts/tts-main", "zz-test-provider/stt/stt-global"]
    assert loose["models"][0]["matched_as"]["match"] == "exact_name"
    stt = loose["models"][1]["matched_as"]
    assert stt["match"] == "partial" and stt["other_candidates"] == ["zz-test-provider/stt/stt-eu"]  # default first
    assert "zz-test-provider/tts/tts-main" in loose["missing"][0]["did_you_mean"]
    assert loose["missing"][1] == {"query": "nonexistent foo", "did_you_mean": []}
    assert "matched_as" not in m.compare_models(["zz-test-provider/tts/tts-main"])["models"][0]
    # cost maths: $30/1M chars x 2M chars = $60; TTS by minutes uses the stated chars/min assumption
    est = m.estimate_cost(["zz-test-provider/tts/tts-main"], characters=2_000_000)
    assert est["lines"][0]["cost_usd"] == 60.0 and est["total_complete"]
    by_min = m.estimate_cost(["zz-test-provider/tts/tts-main"], audio_minutes=100, tts_chars_per_minute=1000)
    assert by_min["lines"][0]["characters"] == 100_000 and by_min["lines"][0]["cost_usd"] == 3.0
    assert "1000 characters per minute" in by_min["lines"][0]["assumption"]
    half = m.estimate_cost(["zz-test-provider/tts/tts-main"], audio_minutes=100, tts_chars_per_minute=1000, tts_share=0.5)
    assert half["lines"][0]["cost_usd"] == 1.5 and "speaking 50% of the time" in half["lines"][0]["assumption"]
    pipe = m.estimate_cost(["zz-test-provider/stt/stt-eu", "zz-test-provider/tts/tts-main"], audio_minutes=60)
    assert pipe["total_complete"] is False and "no per-unit price" in pipe["lines"][0]["note"]   # STT unpriced
    assert m.estimate_cost(["zz-test-provider/tts/tts-main"])["error"]
    # unpriced models say why, never look free
    s = m.search_models(type="stt")["results"]
    assert all(x["price"] is None and x["price_note"].startswith("no per-unit price published") for x in s)
    # alternatives: same type, ranked by language coverage
    alt = m.find_alternatives("zz-test-provider/stt/stt-eu")
    assert [a["key"] for a in alt["alternatives"]] == ["zz-test-provider/stt/stt-global"]
    assert alt["alternatives"][0]["languages_covered"] == "0/1"
    assert m.find_alternatives("nothing like this")["error"] == "model not found"
    # paging
    p1 = m.search_voices(limit=1)
    p2 = m.search_voices(limit=1, offset=p1["next_offset"])
    assert p1["results"][0]["id"] != p2["results"][0]["id"] and p1["total"] == p2["total"]



async def test_agent_review_fixes(tmp_path, client):
    from datetime import date, timedelta

    from tests.conftest import build_fixture_catalog
    from voicedex.catalog.files import ProviderData, write_provider_dir
    from voicedex.catalog.schema import Model, Provider
    from voicedex.catalog.store import Catalog
    from voicedex.main import app
    build_fixture_catalog(tmp_path)
    soon = (date.today() + timedelta(days=30)).isoformat()
    write_provider_dir(tmp_path / "zz-stream", ProviderData(Provider(id="zz-stream", name="ZZ Stream", type="both"), models=[
        Model(id="live-stt", name="Live STT", type="stt", languages=["en-US", "en-GB", "fr-FR"], streaming=True,
              pricing={"unit": "minute", "price_usd": 0.004, "variants": [
                  {"applies_to": "pre-recorded, Pay as you go", "unit": "minute", "price_usd": 0.004},
                  {"applies_to": "streaming, monolingual, Pay as you go", "unit": "minute", "price_usd": 0.006},
                  {"applies_to": "streaming, Growth plan", "unit": "minute", "price_usd": 0.005}]}),
        Model(id="cheap-ending", name="Cheap Ending", type="tts", languages=["en-US"], eol_date=soon,
              pricing={"unit": "character", "price_usd": 0.000001}),
        Model(id="mystery", name="Mystery", type="tts", languages=[])], voices=[]))
    app.state.catalog = Catalog.load(tmp_path)

    # 1. streaming comes from the record's flag, not only from interfaces
    live = m.get_model("zz-stream/stt/live-stt")
    assert live["streaming"] is True and live["record"]["languages"] == ["en", "fr"]
    assert live["record"]["regional_language_variants"] == 3
    assert m.get_model("zz-stream/stt/live-stt", detail="full")["record"]["languages"] == ["en-US", "en-GB", "fr-FR"]
    # 2. a voice-agent estimate (STT + TTS) uses the pay-as-you-go streaming rate; batch mode the headline
    pipe = m.estimate_cost(["zz-stream/stt/live-stt", "zz-test-provider/tts/tts-main"], audio_minutes=100)
    stt_line = pipe["lines"][0]
    assert pipe["mode"] == "streaming" and stt_line["cost_usd"] == 0.6 and "Pay as you go" in stt_line["rate_used"]
    batch = m.estimate_cost(["zz-stream/stt/live-stt", "zz-test-provider/tts/tts-main"], audio_minutes=100, mode="batch")
    assert batch["lines"][0]["cost_usd"] == 0.4 and batch["lines"][0]["rate_used"] == "headline"
    assert m.estimate_cost(["zz-stream/stt/live-stt"], audio_minutes=100)["mode"] == "batch"   # STT alone: headline
    # 3. upcoming shutdowns are searchable; cheapest-first lists push them down
    ending = m.search_models(eol_before=(date.today() + timedelta(days=90)).isoformat())
    assert [x["key"] for x in ending["results"]] == ["zz-stream/tts/cheap-ending"]
    assert ending["results"][0]["shutting_down_in_days"] == 30
    assert m.search_models(shutting_down=True)["total"] == 1
    cheapest = [x["key"] for x in m.search_models(type="tts")["results"]]
    assert cheapest.index("zz-test-provider/tts/tts-main") < cheapest.index("zz-stream/tts/cheap-ending")  # despite $1 vs $30
    assert m.search_models(eol_before="next week")["error"]
    # 6. unknown languages are null, not 0
    mystery = m.get_model("zz-stream/tts/mystery")
    assert mystery["languages"] is None and mystery["price_note"].startswith("no per-unit price published")


def test_resolver_version_order():
    from voicedex.catalog.files import ProviderData
    from voicedex.catalog.schema import Model, Provider
    from voicedex.catalog.store import Catalog, ModelRow
    ids = ["flash_v2", "flash_v2_5", "flash_v2_5-2026-01-12"]
    cat = Catalog({"acme": ProviderData(Provider(id="acme", name="Acme", type="tts"), [], [])},
                  [ModelRow("acme", Model(id=i, name=i, type="tts")) for i in ids], [])
    r, info = m.resolve_model(cat, "acme flash")
    assert r.model.id == "flash_v2_5" and info["other_candidates"][-1] == "acme/tts/flash_v2"


def test_review_round3_helpers():
    # every named replacement is found; the one the notice says the provider recommends comes first
    named = m._named_replacements("gemini-3.8-flash-tts or gemini-3.8-flash-lite-tts",
                                  "Google recommends gemini-3.8-flash-lite-tts as the replacement.")
    assert named == ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"]
    assert m._named_replacements("simba-3.5 (or simba-3.2 for English only)", None) == ["simba-3.5", "simba-3.2"]
    assert m._named_replacements(None, None) == []


async def test_review_round3_tools(tmp_path, client):
    from datetime import date, timedelta

    from tests.conftest import build_fixture_catalog
    from voicedex.catalog.files import ProviderData, write_provider_dir
    from voicedex.catalog.schema import Model, Provider
    from voicedex.catalog.store import Catalog
    from voicedex.main import app
    build_fixture_catalog(tmp_path)
    d = lambda n: (date.today() + timedelta(days=n)).isoformat()   # noqa: E731
    price = {"unit": "character", "price_usd": 0.00001}
    write_provider_dir(tmp_path / "zz-snap", ProviderData(Provider(id="zz-snap", name="ZZ Snap", type="tts"), models=[
        Model(id="voice", name="Voice", type="tts", alias_of="voice-2026-01-01", eol_date=d(60), pricing=price),
        Model(id="voice-2026-01-01", name="Voice 2026-01-01", type="tts", family="voice", snapshot_date="2026-01-01",
              eol_date=d(60), pricing=price),
        Model(id="cheap-late", name="Cheap Late", type="tts", eol_date=d(80), pricing={"unit": "character", "price_usd": 1e-6}),
        Model(id="old", name="Old", type="tts", eol_date=d(3), pricing=price,
              meta={"replacement": "new-a or new-b", "deprecation_notice": "We recommend new-b."}),
        Model(id="new-a", name="New A", type="tts", pricing=price),
        Model(id="new-b", name="New B", type="tts", pricing=price)], voices=[]))
    app.state.catalog = Catalog.load(tmp_path)
    ending = m.search_models(shutting_down=True)
    assert ending["sort"] == "eol_date" and [x["id"] for x in ending["results"]] == ["old", "voice", "cheap-late"]
    assert ending["results"][1]["snapshots"] == ["zz-snap/tts/voice-2026-01-01"]          # alias represents it
    assert m.search_models(shutting_down=True, collapse_snapshots=False)["total"] == 4
    alt = m.find_alternatives("zz-snap/tts/old")
    assert alt["provider_recommends"] == "new-b"
    assert [a["id"] for a in alt["alternatives"][:2]] == ["new-b", "new-a"]
    assert alt["alternatives"][0]["recommended_by_provider"] and alt["alternatives"][1]["announced_replacement"]


async def test_streaming_filters_and_rich_compare(tmp_path, client):
    from tests.conftest import build_fixture_catalog
    from voicedex.catalog.files import ProviderData, write_provider_dir
    from voicedex.catalog.schema import Model, Provider
    from voicedex.catalog.store import Catalog
    from voicedex.main import app
    build_fixture_catalog(tmp_path)
    write_provider_dir(tmp_path / "zz-cmp", ProviderData(Provider(id="zz-cmp", name="ZZ Cmp", type="stt"), models=[
        Model(id="live", name="Live", type="stt", languages=["en-US"], streaming=True, batch=False,
              interfaces=["websocket"], regions=["us"], capabilities=["word_timestamps", "speaker_diarization"],
              meta={"capability_notes": {"speaker_diarization": "pre-recorded only"}}),
        Model(id="files", name="Files", type="stt", languages=["en-US", "de-DE"], streaming=False, batch=True,
              regions=["eu"], max_audio_seconds=7200, capabilities=["word_timestamps"])], voices=[]))
    app.state.catalog = Catalog.load(tmp_path)
    keys = lambda r: {x["key"] for x in r["results"]}                      # noqa: E731
    assert keys(m.search_models(provider="zz-cmp", streaming=True)) == {"zz-cmp/stt/live"}
    assert keys(m.search_models(provider="zz-cmp", streaming=False)) == {"zz-cmp/stt/files"}
    assert keys(m.search_models(provider="zz-cmp", batch=True)) == {"zz-cmp/stt/files"}
    assert keys(m.search_models(type="stt", batch=True)) == {"zz-cmp/stt/files"}   # unknown batch excluded
    cmp = m.compare_models(["zz-cmp/stt/live", "zz-cmp/stt/files"])
    live, files = cmp["models"]
    assert live["interfaces"] == ["websocket"] and live["capability_notes"] == {"speaker_diarization": "pre-recorded only"}
    assert files["max_audio_seconds"] == 7200 and files["regions"] == ["eu"] and files["batch"] is True
    diffs = cmp["differences"]
    assert any(d.startswith("streaming: live = True; files = False") for d in diffs)
    assert any(d.startswith("regions:") for d in diffs) and any(d.startswith("languages: live = 1; files = 2") for d in diffs)
    assert "speaker_diarization: listed only by live" in diffs
    assert not any(d.startswith("word_timestamps") for d in diffs)          # both list it: not a difference
    assert m.compare_models(["zz-cmp/stt/live"])["differences"] == []


async def test_search_voices_facets(client):                         # `client` installs the fixture catalog
    names = lambda r: [x["name"] for x in r["results"]]                 # noqa: E731
    assert names(m.search_voices(accent="british")) == ["Anywhere Voice"]      # case-insensitive, normalized
    assert names(m.search_voices(accent="Indian")) == ["Hindi Voice"]
    assert names(m.search_voices(emotion=True)) == ["Anywhere Voice"]
    assert names(m.search_voices(multilingual=True)) == ["Anywhere Voice"]     # languages=["*"]
    assert m.search_voices(use_case="Narration")["results"] == []              # no use-case data: never matches
    r = m.search_voices(accent="british", emotion=True)
    assert "accent=British" in r["browse_url"] and "emotion=1" in r["browse_url"]
    assert {"age", "use_cases"} <= set(r["results"][0])
