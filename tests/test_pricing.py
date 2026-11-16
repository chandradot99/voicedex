"""Pricing currency rules and the apply_pricing docs pass."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from naaviq.catalog.files import ProviderData, read_provider_dir, write_provider_dir
from naaviq.catalog.schema import Model, Pricing, Provider


def test_currency_rules():
    assert Pricing(unit="minute", price=0.01).price_usd == 0.01            # USD default: price → price_usd
    inr = Pricing(unit="minute", currency="inr", price=0.49)
    assert inr.currency == "INR" and inr.price_usd is None
    with pytest.raises(ValidationError):
        Pricing(unit="minute", currency="EUR", price_usd=0.2)               # never a converted USD figure
    with pytest.raises(ValidationError):
        Pricing(unit="minute")


def _load_script():
    path = Path(__file__).resolve().parent.parent / "scripts" / "apply_docs.py"
    spec = importlib.util.spec_from_file_location("apply_docs", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["apply_docs"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_apply_docs_pricing(tmp_path, monkeypatch):
    mod = _load_script()
    data = tmp_path / "data"
    write_provider_dir(data / "acme", ProviderData(
        Provider(id="acme", name="Acme", type="stt"),
        models=[Model(id="m1", name="M1", type="stt")]))
    cache = tmp_path / ".sync-cache"
    cache.mkdir()
    (cache / "acme_pricing.json").write_text(json.dumps([
        {"model_id": "m1", "type": "stt", "pricing": {"unit": "hour", "price_usd": 0.12}},
        {"model_id": "ghost", "type": "stt", "pricing": {"unit": "hour", "price_usd": 1}},
    ]))
    monkeypatch.setattr(mod, "CACHE", cache)
    assert mod.apply("acme", data, write=True) == 1          # unknown id reported
    m = read_provider_dir(data / "acme").models[0]
    assert m.pricing.price_usd == 0.12 and m.updated_at is not None


def test_apply_docs_capabilities(tmp_path, monkeypatch):
    mod = _load_script()
    data = tmp_path / "data"
    write_provider_dir(data / "acme", ProviderData(
        Provider(id="acme", name="Acme", type="stt"),
        models=[Model(id="m1", name="M1", type="stt")]))
    cache = tmp_path / ".sync-cache"
    cache.mkdir()
    (cache / "acme_docs.json").write_text(json.dumps([
        {"model_id": "m1", "type": "stt", "capabilities": ["speaker_diarization", "punctuation"],
         "capability_notes": {"punctuation": "smart_format"}, "source_urls": ["https://x"]}]))
    monkeypatch.setattr(mod, "CACHE", cache)
    assert mod.apply("acme", data, write=True) == 0
    m = read_provider_dir(data / "acme").models[0]
    assert m.capabilities == ["punctuation", "speaker_diarization"]
    assert m.meta["capability_notes"] == {"punctuation": "smart_format"} and m.meta["docs_sources"] == ["https://x"]
    (cache / "acme_docs.json").write_text(json.dumps([
        {"model_id": "m1", "type": "stt", "capabilities": ["voice_cloning"]}]))   # TTS term on STT model
    assert mod.apply("acme", data, write=True) == 1
