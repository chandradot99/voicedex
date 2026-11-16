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
