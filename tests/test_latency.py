"""Vendor latency claims and benchmark links: schema rules, wording, apply_docs, API and MCP."""
import json

import pytest

from tests.conftest import TEST_PROVIDER
from voicedex.catalog.files import read_provider_dir
from voicedex.catalog.schema import Model
from voicedex.web import views

LAT = {"ms": 75, "metric": "time_to_first_audio", "source_url": "u"}


def test_schema_rules():
    with pytest.raises(ValueError, match="doesn't fit a stt model"):
        Model(id="a", name="A", type="stt", latency=LAT)
    with pytest.raises(ValueError, match="unknown latency qualifier"):
        Model(id="a", name="A", type="tts", latency={**LAT, "qualifier": "blazing"})
    with pytest.raises(ValueError, match="unknown benchmark"):
        Model(id="a", name="A", type="tts", benchmarks=[{"name": "vibes", "url": "u"}])
    with pytest.raises(ValueError, match="one link per benchmark"):
        Model(id="a", name="A", type="tts", benchmarks=[{"name": "tts_arena", "url": "u"}] * 2)


@pytest.mark.parametrize("q,ms,want", [("typical", 75, "~75 ms to first audio"),
                                       ("under", 300, "under 300 ms to first audio"),
                                       ("as_low_as", 40, "as low as 40 ms to first audio"),
                                       ("p90", 1200, "1.2 s p90 to first audio")])
def test_label(q, ms, want):
    assert views.latency_label(Model(id="a", name="A", type="tts", latency={**LAT, "ms": ms, "qualifier": q})) == want


def test_apply_docs_keeps_date_of_unchanged_claim(tmp_path, monkeypatch):
    import scripts.apply_docs as ad
    from tests.conftest import build_fixture_catalog
    build_fixture_catalog(tmp_path / "data")
    monkeypatch.setattr(ad, "CACHE", tmp_path, raising=False)
    row = {"model_id": "stt-global", "type": "stt",
           "latency": {"ms": 300, "metric": "transcript_latency", "qualifier": "under", "source_url": "https://x"},
           "benchmarks": [{"name": "open_asr_leaderboard", "url": "https://hf.example/asr"}]}
    src = tmp_path / f"{TEST_PROVIDER}_docs.json"
    src.write_text(json.dumps([row]))
    assert ad.apply(TEST_PROVIDER, tmp_path / "data", True) == 0
    m = next(m for m in read_provider_dir(tmp_path / "data" / TEST_PROVIDER).models if m.id == "stt-global")
    assert m.latency.ms == 300 and m.benchmarks[0].name == "open_asr_leaderboard"
    first = (m.latency.as_of, m.updated_at)
    src.write_text(json.dumps([{**row, "latency": {**row["latency"], "as_of": "2030-01-01"}}]))
    assert ad.apply(TEST_PROVIDER, tmp_path / "data", True) == 0
    m = next(m for m in read_provider_dir(tmp_path / "data" / TEST_PROVIDER).models if m.id == "stt-global")
    assert (m.latency.as_of, m.updated_at) == first          # same claim: no date churn
    bad = {**row, "latency": {**row["latency"], "metric": "time_to_first_audio"}}
    src.write_text(json.dumps([bad]))
    assert ad.apply(TEST_PROVIDER, tmp_path / "data", True) == 1


async def test_api_and_mcp(client, fixture_catalog, monkeypatch):
    m = (await client.get(f"/v1/providers/{TEST_PROVIDER}/models/tts-main")).json()
    assert m["latency"]["ms"] == 75 and m["benchmarks"][0]["name"] == "tts_arena"
    from voicedex import mcp_server as mcp
    monkeypatch.setattr(mcp, "_cat", lambda: fixture_catalog)
    got = mcp.get_model(f"{TEST_PROVIDER}/tts/tts-main")
    assert got["vendor_latency_claim"] == "~75 ms to first audio"
    assert got["benchmarks"] == [{"name": "TTS Arena", "url": "https://arena.example/zz"}]
    page = (await client.get(f"/models/{TEST_PROVIDER}/tts/tts-main")).text
    assert "~75 ms to first audio" in page and "Not measured by us" in page and "TTS Arena" in page
