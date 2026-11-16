"""Merge rules (design D4/D7): added / unchanged / updated / deprecated / revived, unknown-keeping, guard."""

from __future__ import annotations

from datetime import date

import pytest

from naaviq.catalog.files import ProviderData, read_provider_dir, write_provider_dir
from naaviq.catalog.merge import GuardError, merge
from naaviq.sync.base import SyncModel, SyncResult, SyncVoice

D1, D2, D3 = date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)


def _result(models=(), voices=(), source="api") -> SyncResult:
    stt = [m for m in models if m.type == "stt"]
    tts = [m for m in models if m.type == "tts"]
    return SyncResult(stt_models=stt, tts_models=tts, tts_voices=list(voices), source=source,
                      api_urls=["https://api.example/models"], docs_urls=["https://docs.example"])


def _run(current, result, today, **kw) -> tuple[ProviderData, object]:
    return merge(current, result, provider_id="acme", display_name="Acme", seeded_type="tts", today=today, **kw)


def _tts(i, **kw) -> SyncModel:
    kw.setdefault("display_name", f"M{i}")
    return SyncModel(model_id=f"m{i}", type="tts", **kw)


def _models(pd):
    return {m.id: m for m in pd.models}


def test_first_sync_adds_everything_with_dates():
    pd, rep = _run(None, _result([_tts(1, is_default=True)], [SyncVoice("v1", "V1")]), D1)
    m = _models(pd)["m1"]
    assert (m.first_seen, m.updated_at, m.is_default) == (D1, D1, True)
    assert m.provenance.method == "api" and m.provenance.as_of == D1
    assert pd.provider.type == "tts" and pd.provider.last_synced == D1
    assert rep.counts() == {"tts": {"added": 1}, "voices": {"added": 1}}


def test_unchanged_record_keeps_dates():
    pd, _ = _run(None, _result([_tts(1)]), D1)
    pd2, rep = _run(pd, _result([_tts(1)]), D2)
    assert _models(pd2)["m1"].updated_at == D1
    assert not rep.has_changes


def test_changed_record_gets_updated_at_and_field_diff():
    pd, _ = _run(None, _result([_tts(1)]), D1)
    pd2, rep = _run(pd, _result([_tts(1, display_name="M1 v2")]), D2)
    m = _models(pd2)["m1"]
    assert (m.name, m.first_seen, m.updated_at) == ("M1 v2", D1, D2)
    assert rep.changes[0].fields == {"name": ("M1", "M1 v2")}


def test_empty_incoming_values_do_not_erase_known_data():
    pricing = {"unit": "character", "price_usd": 0.0001}
    pd, _ = _run(None, _result([_tts(1, pricing=pricing, capabilities=["ssml"], description="d")]), D1)
    pd2, rep = _run(pd, _result([_tts(1)]), D2)  # docs page forgot pricing/caps/description
    m = _models(pd2)["m1"]
    assert m.pricing.price_usd == 0.0001 and m.capabilities == ["ssml"] and m.description == "d"
    assert not rep.has_changes


def test_missing_records_are_deprecated_not_deleted_then_revived():
    many = [_tts(i) for i in range(1, 6)]
    pd, _ = _run(None, _result(many), D1)
    pd2, rep = _run(pd, _result(many[:4]), D2)  # 1/5 = 20% ≤ guard limit
    gone = _models(pd2)["m5"]
    assert (gone.lifecycle, gone.deprecated_at) == ("deprecated", D2)
    assert rep.counts() == {"tts": {"deprecated": 1}}

    pd3, rep = _run(pd2, _result(many), D3)
    back = _models(pd3)["m5"]
    assert (back.lifecycle, back.deprecated_at, back.updated_at) == ("ga", None, D3)
    assert rep.counts() == {"tts": {"revived": 1}}


def test_guard_blocks_empty_fetch():
    pd, _ = _run(None, _result([_tts(1)], [SyncVoice("v1", "V1")]), D1)
    with pytest.raises(GuardError, match="returned nothing"):
        _run(pd, _result([_tts(1)], []), D2)


def test_guard_blocks_mass_deprecation_unless_allowed():
    many = [_tts(i) for i in range(1, 9)]
    pd, _ = _run(None, _result(many), D1)
    with pytest.raises(GuardError, match="partial fetch"):
        _run(pd, _result(many[:4]), D2)
    pd2, _ = _run(pd, _result(many[:4]), D2, allow_shrink=True)
    assert sum(m.deprecated_at is not None for m in pd2.models) == 4


def test_deprecated_default_is_cleared_so_new_default_is_unique():
    pd, _ = _run(None, _result([_tts(1, is_default=True), _tts(2), _tts(3), _tts(4)]), D1)
    pd2, _ = _run(pd, _result([_tts(2, is_default=True), _tts(3), _tts(4)]), D2)
    defaults = [m.id for m in pd2.models if m.is_default]
    assert defaults == ["m2"]


def test_rejects_two_defaults_and_duplicates():
    with pytest.raises(ValueError, match="more than one default"):
        _run(None, _result([_tts(1, is_default=True), _tts(2, is_default=True)]), D1)
    with pytest.raises(ValueError, match="duplicate model"):
        _run(None, _result([_tts(1), _tts(1)]), D1)


def test_rejects_unknown_capability_and_drops_wrong_modality():
    with pytest.raises(ValueError, match="unknown model capability"):
        _run(None, _result([_tts(1, capabilities=["telepathy"])]), D1)
    pd, _ = _run(None, _result([SyncModel("s", "S", "stt", capabilities=["emotion", "punctuation"])]), D1)
    assert pd.models[0].capabilities == ["punctuation"]


def test_meta_family_hints_become_first_class_fields():
    m = _tts(1, meta={"parent_model_id": "sonic-3", "snapshot_date": "2026-01-12", "is_snapshot": True, "x": 1})
    pd, _ = _run(None, _result([m]), D1)
    rec = pd.models[0]
    assert (rec.family, str(rec.snapshot_date), rec.meta) == ("sonic-3", "2026-01-12", {"x": 1})


def test_docs_sourced_models_get_docs_provenance():
    pd, _ = _run(None, _result([_tts(1, source="docs")], source="mixed"), D1)
    assert pd.models[0].provenance.method == "docs"
    assert pd.models[0].provenance.urls == ["https://docs.example"]


def test_files_round_trip(tmp_path):
    pd, _ = _run(None, _result([_tts(1, languages=["no"])], [SyncVoice("v1", "V1", accent="British")]), D1)
    write_provider_dir(tmp_path / "acme", pd)
    again = read_provider_dir(tmp_path / "acme")
    assert again.models == pd.models and again.voices == pd.voices
    assert again.models[0].languages == ["no"]  # Norwegian survives (the YAML "no" problem)
