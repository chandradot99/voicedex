"""Provider verification: the provider confirmed its listing; later changes are shown as changed since."""

from datetime import date

from voicedex.catalog.files import ProviderData, write_provider_dir
from voicedex.catalog.schema import Model, Provider
from voicedex.catalog.store import Catalog
from voicedex.main import app
from voicedex.web import views


def _catalog(tmp_path):
    write_provider_dir(tmp_path / "zz-ver", ProviderData(
        Provider(id="zz-ver", name="ZZ Ver", type="stt",
                 verified={"on": "2026-11-19", "by": "ZZ developer relations", "scope": ["pricing"]}),
        models=[Model(id="old", name="Old", type="stt", languages=["en-US"], updated_at=date(2026, 11, 19)),
                Model(id="new", name="New", type="stt", languages=["en-US"], updated_at=date(2026, 12, 1))],
        voices=[]))
    return Catalog.load(tmp_path)


def test_verification_status_counts_changes_since(tmp_path):
    s = views.verification_status(_catalog(tmp_path), "zz-ver")
    assert (s.by, s.on, s.scope, s.changed_models, s.changed_voices) == (
        "ZZ developer relations", "2026-11-19", ["pricing"], 1, 0)


async def test_verified_badge_on_pages(tmp_path, client):
    app.state.catalog = _catalog(tmp_path)
    page = (await client.get("/providers/zz-ver")).text
    assert "Verified by ZZ Ver</a> on <span class=\"mono\">2026-11-19</span>: pricing." in page
    assert "Since then 1 model changed." in page
    assert "Verified by ZZ Ver</a> on" in (await client.get("/models/zz-ver/stt/old")).text
    assert "this model changed after that" in (await client.get("/models/zz-ver/stt/new")).text
    api = (await client.get("/v1/providers/zz-ver")).json()
    assert api["verified"]["on"] == "2026-11-19"
