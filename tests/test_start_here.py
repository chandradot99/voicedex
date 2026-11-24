"""Model lineage fields (released_on / recommended / replaces) and the provider page "Start here" header."""

from datetime import date

import pytest
from pydantic import ValidationError

from voicedex.catalog.files import ProviderData, write_provider_dir
from voicedex.catalog.merge import _pop_lineage, partial_date
from voicedex.catalog.schema import Model, Provider
from voicedex.catalog.store import Catalog
from voicedex.main import app
from voicedex.web import views


@pytest.mark.parametrize("raw, want", [
    ("2026-04-17", "2026-04-17"), ("2026-04", "2026-04"), ("2026", "2026"), ("June 2026", "2026-06"),
    (date(2026, 1, 2), "2026-01-02"), ("2026-13", None), ("soon", None), (None, None),
])
def test_partial_date(raw, want):
    assert partial_date(raw) == want


def test_released_on_rejects_bad_dates():
    with pytest.raises(ValidationError):
        Model(id="m", name="M", type="tts", released_on="2026-4")


def test_lineage_promoted_from_meta():
    meta = {"release_date": "March 2026", "recommended_for": "voice agents", "replaces": "old", "x": 1}
    assert _pop_lineage(meta) == {"released_on": "2026-03", "recommended_for": "voice agents",
                                  "recommended": True, "replaces": ["old"]}
    assert meta == {"x": 1}
    # an explicit "legacy" verdict is not overridden by a recommended_for string
    assert _pop_lineage({"recommended": False, "recommended_for": "x"})["recommended"] is False
    # unparseable dates stay in meta
    meta = {"released": "Q3"}
    assert _pop_lineage(meta) == {} and meta == {"released": "Q3"}


def _catalog(tmp_path):
    def tts(i, **kw):
        return Model(id=i, name=i.upper(), type="tts", languages=kw.pop("languages", ["en-US"]), **kw)
    write_provider_dir(tmp_path / "zz-sh", ProviderData(
        Provider(id="zz-sh", name="ZZ SH", type="tts"),
        models=[
            tts("v1", recommended=False, capabilities=["ssml"],
                pricing={"unit": "character", "price_usd": 0.00002}),
            tts("v2", recommended=True, recommended_for="audiobooks", released_on="2026-05",
                description="Our most expressive model. It also sings.", languages=["en-US", "de-DE", "fr-FR"],
                capabilities=["ssml", "emotion"], replaces=["v1"],
                pricing={"unit": "character", "price_usd": 0.00003}),
            tts("v2-fast", recommended=True, released_on="2026-07", is_default=True),
            tts("ending", recommended=True, eol_date=date(2026, 12, 1)),
        ],
        voices=[]))
    write_provider_dir(tmp_path / "zz-none", ProviderData(
        Provider(id="zz-none", name="ZZ None", type="tts"),
        models=[tts("only", is_default=True)], voices=[]))
    return Catalog.load(tmp_path)


def test_start_here_picks_only_recommended_newest_first(tmp_path):
    cat = _catalog(tmp_path)
    s = views.start_here(cat, "zz-sh")
    (t, picks), = s.groups
    assert t == "tts" and [p.row.model.id for p in picks] == ["v2-fast", "v2"]   # eol'd one left out
    assert s.rest == {"tts": 2}
    v2 = picks[1]
    assert v2.summary == "Most expressive model"
    assert v2.use == "audiobooks"
    assert v2.features == ["Emotion control", "SSML"]
    d = v2.delta
    assert (d.old.model.id, d.languages, d.added, d.removed, d.price) == ("v1", 2, ["Emotion control"], [], "1.5× the price")
    # no recommendation → no header, never a guessed flagship (even with a default model)
    assert views.start_here(cat, "zz-none") is None


def test_share_phrase_reads_from_the_majority_side():
    assert views._share_phrase(15, 5, 20, "cheaper than", "cost less", "TTS models") == "cheaper than 75% of TTS models"
    assert views._share_phrase(4, 16, 20, "cheaper than", "cost less", "TTS models") == "80% of TTS models cost less"
    assert views._share_phrase(4, 6, 10, "cheaper than", "cost less", "TTS models") is None   # too few peers


async def test_start_here_on_provider_page(tmp_path, client):
    app.state.catalog = _catalog(tmp_path)
    page = (await client.get("/providers/zz-sh")).text
    assert "Start here" in page and "released 2026-05" in page and "vs <a" in page
    assert "Start here" not in (await client.get("/providers/zz-none")).text
    api = (await client.get("/v1/providers/zz-sh/models/v2")).json()
    assert (api["released_on"], api["recommended"], api["replaces"]) == ("2026-05", True, ["v1"])
