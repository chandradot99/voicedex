"""HTML catalog pages render from the in-memory catalog and respect filters."""

from voicedex.catalog.schema import Model
from voicedex.web.views import heat_level, language_name, normalized_price


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
    from voicedex.catalog.schema import Voice
    from voicedex.web.views import voice_chips
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
    from voicedex.web.views import price_label
    m = Model(id="f", name="f", type="tts", pricing={"unit": "character", "price_usd": 0})
    assert price_label(m) == "Free"


async def test_openapi_examples_use_real_data(client):
    from voicedex.main import app
    app.openapi_schema = None                      # rebuild against the fixture catalog
    spec = (await client.get("/openapi.json")).json()
    ex = spec["paths"]["/v1/models"]["get"]["responses"]["200"]["content"]["application/json"]["example"]
    assert ex["data"] and ex["data"][0]["provider_id"] == "zz-test-provider" and ex["data"][0]["model_id"] != "string"
    params = {p["name"]: p.get("example") for p in spec["paths"]["/v1/providers/{provider_id}/models/{model_id}"]["get"]["parameters"]}
    assert params["provider_id"] == "zz-test-provider" and params["model_id"]
    err = spec["paths"]["/v1/models"]["get"]["responses"]["422"]["content"]["application/json"]["example"]
    assert err["detail"][0]["loc"] == ["query", "limit"]
    app.openapi_schema = None


async def test_robots_and_sitemap(client):
    robots = (await client.get("/robots.txt")).text
    assert "Disallow: /search" in robots and "Sitemap: https://voicedex.dev/sitemap.xml" in robots
    r = await client.get("/sitemap.xml")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/xml")
    assert "<loc>https://voicedex.dev/providers/zz-test-provider</loc>" in r.text
    assert "/models/zz-test-provider/stt/stt-eu" in r.text
    assert "tts-old" not in r.text                                    # deprecated models are left out


async def test_canonical_and_share_tags(client):
    html = (await client.get("/models?type=stt")).text
    assert '<link rel="canonical" href="https://voicedex.dev/models">' in html     # filters dropped
    assert 'og:image" content="https://voicedex.dev/static/og.png"' in html
    assert (await client.get("/static/og.png")).status_code == 200


def test_rate_limit_key_cloudflare(monkeypatch):
    from starlette.requests import Request

    from voicedex.config import settings
    from voicedex.limiter import client_ip

    req = Request({"type": "http", "headers": [(b"x-forwarded-for", b"1.1.1.1, 172.64.0.9"),
                                               (b"cf-connecting-ip", b"203.0.113.7")], "client": ("10.0.0.1", 1)})
    assert client_ip(req) == "172.64.0.9"                # default: never trust a client-settable header
    monkeypatch.setattr(settings, "trust_cf_connecting_ip", True)
    assert client_ip(req) == "203.0.113.7"


async def test_gzip_and_page_caching(client):
    r = await client.get("/v1/catalog.json", headers={"Accept-Encoding": "gzip"})
    assert r.headers["content-encoding"] == "gzip" and "ETag" in r.headers
    page = await client.get("/models")
    assert page.headers["cache-control"] == "public, max-age=300" and "etag" not in page.headers
    assert (await client.get("/health")).headers["cache-control"] == "no-store"
