"""HTML catalog pages render from the in-memory catalog and respect filters."""

from naaviq.catalog.schema import Model
from naaviq.web.views import heat_level, language_name, normalized_price


async def test_pages_render(client):
    for path in ("/", "/providers/zz-test-provider", "/providers/zz-test-deprecated", "/models", "/voices",
                 "/search?q=hindi", "/search?q=zz", "/static/site.css"):
        r = await client.get(path)
        assert r.status_code == 200, path


async def test_home_lists_retired_and_active(client):
    html = (await client.get("/")).text
    assert "ZZ Test" in html and "No longer available" in html


async def test_model_filters(client):
    html = (await client.get("/models?type=stt&language=de")).text
    assert "stt-eu" in html and "tts-main" not in html
    assert "tts-old" not in (await client.get("/models")).text      # deprecated hidden


async def test_voice_filters(client):
    html = (await client.get("/voices?gender=male")).text
    assert "Hindi Voice" in html and "Anywhere Voice" not in html


async def test_unknown_provider_404(client):
    assert (await client.get("/providers/nope")).status_code == 404


def test_helpers():
    assert language_name("hi") == "Hindi" and language_name("*") == "Many languages"
    m = Model(id="x", name="x", type="tts", pricing={"unit": "character", "price_usd": 0.00003})
    assert normalized_price(m) == (30.0, "per 1M chars")
    s = Model(id="s", name="s", type="stt", pricing={"unit": "minute", "price_usd": 0.004})
    assert round(normalized_price(s)[0], 4) == 0.24
    assert heat_level(0, 10) == 0 and heat_level(1, 10) == 1 and heat_level(50, 50) == 5


async def test_model_page_and_compare(client):
    r = await client.get("/models/zz-test-provider/tts/tts-main")
    assert r.status_code == 200 and "tts-main" in r.text and "Add to compare" in r.text
    assert (await client.get("/models/zz-test-provider/tts/nope")).status_code == 404
    html = (await client.get("/compare?m=zz-test-provider/stt/stt-global&m=zz-test-provider/stt/stt-eu&language=de")).text
    assert "stt-global" in html and "stt-eu" in html and "Supports German" in html
    assert "Speaker diarization" in html                       # feature union row
    empty = (await client.get("/compare")).text
    assert "Nothing to compare yet" in empty


async def test_404_html_for_pages_json_for_api(client):
    page = await client.get("/providers/nope")
    assert page.status_code == 404 and "text/html" in page.headers["content-type"]
    api = await client.get("/v1/providers/nope")
    assert api.status_code == 404 and api.headers["content-type"].startswith("application/json")


async def test_voice_model_filter(client):
    html = (await client.get("/voices?provider=zz-test-provider&model=tts-main")).text
    assert "Hindi Voice" in html and "Anywhere Voice" in html     # explicit id and wildcard both match


def test_voice_chips():
    from naaviq.catalog.schema import Voice
    from naaviq.web.views import voice_chips
    v = Voice(id="x", name="x", use_cases=["use-case:e-learning", "age:young-adult", "narration"], tags=["calm"])
    assert voice_chips(v) == ["e learning", "narration", "calm"]


async def test_api_reference(client):
    r = await client.get("/docs")
    assert r.status_code == 200 and "scalar-docs" in r.text and "@scalar/api-reference@" in r.text
    spec = (await client.get("/openapi.json")).json()
    assert [t["name"] for t in spec["tags"]][:2] == ["Models & voices", "Providers"]
    ops = [op for path in spec["paths"].values() for op in path.values()]
    assert all(op.get("summary") for op in ops) and all(len(op.get("tags", [])) == 1 for op in ops)
    assert (await client.get("/redoc", follow_redirects=False)).status_code == 301


def test_free_price_label():
    from naaviq.web.views import price_label
    m = Model(id="f", name="f", type="tts", pricing={"unit": "character", "price_usd": 0})
    assert price_label(m) == "Free"
