"""Changes feed (git-history diffing, /changes, /changes.xml) and provider-vs-provider pages."""

import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import date

from tests.conftest import TEST_PROVIDER, build_fixture_catalog
from voicedex.catalog.files import ProviderData, write_provider_dir
from voicedex.catalog.schema import Model, Provider
from voicedex.catalog.store import Catalog
from voicedex.main import app
from voicedex.web import changes as ch
from voicedex.web import routes, views


def _m(id, **kw):
    return {"id": id, "type": "tts", "name": id.upper(), **kw}


def test_diff_models_kinds():
    def price(usd):
        return {"unit": "character", "price_usd": usd}

    old = {("tts", "a"): _m("a", pricing=price(1e-5)), ("tts", "b"): _m("b"), ("tts", "c"): _m("c"),
           ("tts", "d"): _m("d", lifecycle="beta"), ("tts", "gone"): _m("gone")}
    new = {("tts", "a"): _m("a", pricing=price(2e-5)), ("tts", "b"): _m("b", eol_date="2027-01-01"),
           ("tts", "c"): _m("c", deprecated_at="2026-11-20"), ("tts", "d"): _m("d", lifecycle="ga"),
           ("tts", "new"): _m("new")}
    got = {(c.kind, c.model_id): c for c in ch.diff_models(old, new, "2026-11-20", "p", "abc")}
    assert set(got) == {("price_changed", "a"), ("shutdown_announced", "b"), ("model_deprecated", "c"),
                        ("now_ga", "d"), ("model_added", "new"), ("model_removed", "gone")}
    assert got[("price_changed", "a")].before == "$10.00 per 1M chars" and got[("price_changed", "a")].after == "$20.00 per 1M chars"
    assert got[("shutdown_announced", "b")].after == "2027-01-01"


def _commit(repo, msg, day):
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    env = {"GIT_AUTHOR_DATE": f"{day}T12:00:00", "GIT_COMMITTER_DATE": f"{day}T12:00:00",
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.com", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", msg], check=True, env=env)


def test_build_changes_replays_history(tmp_path):
    repo = tmp_path
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    d = repo / "data" / "acme"
    d.mkdir(parents=True)

    def write(models):
        (d / "models.json").write_text(json.dumps(models))

    (d / "provider.json").write_text(json.dumps({"id": "acme", "name": "Acme", "status": "active"}))
    write([_m("x", pricing={"unit": "character", "price_usd": 1e-5})])
    _commit(repo, "baseline import", "2026-11-10")                       # before the feed starts: baseline
    write([_m("x", pricing={"unit": "character", "price_usd": 3e-5})])
    _commit(repo, "fix our typo [skip changes]", "2026-11-20")            # a correction: not an event
    write([_m("x", pricing={"unit": "character", "price_usd": 2e-5}), _m("y")])
    _commit(repo, "sync acme", "2026-11-21")
    e = repo / "data" / "newco"
    e.mkdir()
    (e / "provider.json").write_text(json.dumps({"id": "newco", "name": "NewCo"}))
    (e / "models.json").write_text(json.dumps([_m("z")]))
    _commit(repo, "add newco", "2026-11-22")
    got = ch.build_changes(repo, feed_starts=date(2026, 11, 15))
    assert [(c.date, c.kind, c.provider_id, c.model_id) for c in got] == [
        ("2026-11-22", "provider_added", "newco", ""),
        ("2026-11-21", "price_changed", "acme", "x"),
        ("2026-11-21", "model_added", "acme", "y"),
    ]
    assert got[1].before == "$30.00 per 1M chars"          # diffed against the corrected state, not the baseline


FEED = (
    ch.Change(date="2026-11-21", kind="price_changed", provider_id=TEST_PROVIDER, commit="c1", model_type="tts",
              model_id="tts-main", model_name="TTS Main", before="$20.00 per 1M chars", after="$30.00 per 1M chars"),
    ch.Change(date="2026-11-21", kind="provider_added", provider_id="zz-test-deprecated", commit="c1"),
    ch.Change(date="2026-11-20", kind="shutdown_announced", provider_id=TEST_PROVIDER, commit="c0", model_type="stt",
              model_id="stt-eu", model_name="STT EU", after="2027-01-31"),
)


async def test_changes_page_and_atom(client, monkeypatch):
    monkeypatch.setattr(routes, "load_changes", lambda _d: FEED)
    html = (await client.get("/changes")).text
    assert "Price changed" in html and "$20.00 per 1M chars → $30.00 per 1M chars" in html
    assert "1 provider added:" in html and 'href="/models/zz-test-provider/tts/tts-main"' in html
    r = await client.get("/changes.xml")
    assert r.headers["content-type"].startswith("application/atom+xml")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(r.text)
    titles = [e.find("a:title", ns).text for e in root.findall("a:entry", ns)]
    assert "Price changed: ZZ Test TTS Main ($20.00 per 1M chars → $30.00 per 1M chars)" in titles
    assert "1 provider added" in titles and len(titles) == 3
    assert titles[0].startswith("Price changed")     # within 2026-11-21: price change before the providers line
    assert titles[-1].startswith("Shutdown announced")  # 2026-11-20 comes after 2026-11-21
    assert "/changes" in (await client.get("/sitemap.xml")).text


async def test_provider_vs_page(tmp_path, monkeypatch, client):
    build_fixture_catalog(tmp_path)
    write_provider_dir(tmp_path / "zz-rival", ProviderData(
        Provider(id="zz-rival", name="ZZ Rival", type="tts"),
        models=[Model(id="rival-tts", name="Rival TTS", type="tts", languages=["en-US"], capabilities=["ssml"],
                      pricing={"unit": "character", "price_usd": 0.00001})], voices=[]))
    app.state.catalog = Catalog.load(tmp_path)
    monkeypatch.setattr(views, "COMPARE_PROVIDERS", (TEST_PROVIDER, "zz-rival", "zz-test-deprecated"))
    assert views.provider_pairs(app.state.catalog) == [("zz-rival", TEST_PROVIDER)]   # retired one left out
    page = await client.get("/compare/zz-rival-vs-zz-test-provider")
    rev = await client.get("/compare/zz-test-provider-vs-zz-rival", follow_redirects=False)
    assert rev.status_code == 301 and rev.headers["location"] == "/compare/zz-rival-vs-zz-test-provider"
    assert page.status_code == 200 and "<h1>ZZ Rival vs ZZ Test</h1>" in page.text
    assert "ZZ Rival lists 1 text-to-speech model from $10.00 per 1M chars" in page.text
    assert "Only ZZ Test offers speech-to-text models" in page.text
    assert (await client.get("/compare/zz-rival-vs-nope")).status_code == 404
    assert 'href="/compare/zz-rival-vs-zz-test-provider"' in (await client.get("/providers/zz-rival")).text
    sm = (await client.get("/sitemap.xml")).text
    assert "/compare/zz-rival-vs-zz-test-provider" in sm
    robots = (await client.get("/robots.txt")).text
    assert robots.index("Allow: /compare/") < robots.index("Disallow: /compare")


async def test_alternatives_pages(tmp_path, monkeypatch, client):
    build_fixture_catalog(tmp_path)
    write_provider_dir(tmp_path / "zz-rival", ProviderData(
        Provider(id="zz-rival", name="ZZ Rival", type="tts"),
        models=[Model(id="rival-tts", name="Rival TTS", type="tts", languages=["en-US"], capabilities=["ssml"],
                      pricing={"unit": "character", "price_usd": 0.00001})], voices=[]))
    app.state.catalog = Catalog.load(tmp_path)
    monkeypatch.setattr(views, "COMPARE_PROVIDERS", (TEST_PROVIDER, "zz-rival"))
    assert views.alternatives_subjects(app.state.catalog) == ["zz-rival", "zz-test-deprecated", TEST_PROVIDER]
    html = (await client.get(f"/alternatives/{TEST_PROVIDER}")).text
    assert "<h1>ZZ Test alternatives</h1>" in html
    table = html.split('id="alt-tts"', 1)[1]
    assert 'href="/providers/zz-rival"' in table and "1/2" in table          # shares ssml of {emotion, ssml}
    assert "1 list a lower starting price" in html                            # $10 < $30
    assert 'href="/compare/zz-rival-vs-zz-test-provider"' in table
    retired = (await client.get("/alternatives/zz-test-deprecated")).text     # shut down: still gets a page
    assert "ZZ Gone is no longer available" in retired and 'href="/providers/zz-rival"' in retired
    assert (await client.get("/alternatives/nope")).status_code == 404
    index = (await client.get("/alternatives")).text
    assert 'href="/alternatives/zz-test-deprecated"' in index and "Shut down or no longer sold" in index
    assert 'href="/alternatives/zz-rival"' in (await client.get("/providers/zz-rival")).text
    assert "/alternatives/zz-rival</loc>" in (await client.get("/sitemap.xml")).text
