"""Real-data examples for the OpenAPI document (shown in the API reference).

FastAPI would otherwise emit type placeholders ("model_id": "string"). Examples are built from the loaded
catalog with the same serializers the endpoints use, so they always match the live data. Long arrays are
trimmed to keep the reference readable.
"""

from __future__ import annotations

from typing import Any

from naaviq.catalog.schema import SCHEMA_VERSION
from naaviq.catalog.store import Catalog
from naaviq.schemas import ModelOut, ProviderOut, VoiceOut

_PREFERRED_MODELS = [("deepgram", "stt", "nova-3-general"), ("elevenlabs", "tts", "eleven_flash_v2_5"),
                     ("cartesia", "tts", "sonic-3")]
_PREFERRED_PROVIDERS = ["deepgram", "elevenlabs"]
_MAX_LIST = 6


def _trim(obj: Any) -> Any:
    if isinstance(obj, list):
        return [_trim(x) for x in obj[:_MAX_LIST]]
    if isinstance(obj, dict):
        return {k: _trim(v) for k, v in obj.items()}
    return obj


def _active_models(catalog: Catalog):
    return [r for r in catalog.models if r.model.deprecated_at is None]


def _pick_models(catalog: Catalog, n: int = 2):
    rows = _active_models(catalog)
    chosen = [r for key in _PREFERRED_MODELS for r in rows
              if (r.provider_id, str(getattr(r.model.type, "value", r.model.type)), r.model.id) == key]
    for r in rows:                                   # fallback for other catalogs (e.g. tests)
        if len(chosen) >= n:
            break
        if r not in chosen:
            chosen.append(r)
    return chosen[:n]


def _pick_voices(catalog: Catalog, n: int = 2):
    voices = [r for r in catalog.voices if r.voice.deprecated_at is None]
    with_sample = [r for r in voices if r.voice.preview_url and r.provider_id == "elevenlabs"]
    rest = [r for r in voices if r not in with_sample]
    return (with_sample + rest)[:n]


def _provider_out(catalog: Catalog, pid: str) -> dict:
    pd = catalog.providers[pid]
    return ProviderOut.build(
        pd.provider,
        model_count=sum(1 for m in pd.models if m.deprecated_at is None),
        voice_count=sum(1 for v in pd.voices if v.deprecated_at is None),
    ).model_dump(mode="json")


def _set_example(spec: dict, path: str, status: str, example: Any) -> None:
    op = spec.get("paths", {}).get(path, {}).get("get")
    if not op:
        return
    content = op.setdefault("responses", {}).setdefault(status, {}).setdefault("content", {})
    content.setdefault("application/json", {})["example"] = _trim(example)


def _set_param_example(spec: dict, path: str, name: str, value: str) -> None:
    op = spec.get("paths", {}).get(path, {}).get("get")
    for p in (op or {}).get("parameters", []):
        if p.get("name") == name:
            p["example"] = value


def inject_examples(spec: dict, catalog: Catalog) -> dict:
    models = _pick_models(catalog)
    voices = _pick_voices(catalog)
    if not models or not voices:
        return spec
    active_providers = [pid for pid, pd in catalog.providers.items() if pd.provider.status == "active"]
    providers = [p for p in _PREFERRED_PROVIDERS if p in active_providers] or active_providers[:2]

    model_out = [ModelOut.build(r.provider_id, r.model).model_dump(mode="json") for r in models]
    voice_out = [VoiceOut.build(r.provider_id, r.voice).model_dump(mode="json") for r in voices]
    n_models, n_voices = len(_active_models(catalog)), sum(1 for r in catalog.voices if r.voice.deprecated_at is None)

    m0, v0 = models[0], voices[0]
    prov_models = [ModelOut.build(m0.provider_id, r.model).model_dump(mode="json")
                   for r in _active_models(catalog) if r.provider_id == m0.provider_id][:2]
    prov_voices = [VoiceOut.build(v0.provider_id, r.voice).model_dump(mode="json")
                   for r in catalog.voices if r.provider_id == v0.provider_id and r.voice.deprecated_at is None][:2]

    _set_example(spec, "/v1/models", "200",
                 {"total": n_models, "limit": 100, "offset": 0, "data": model_out})
    _set_example(spec, "/v1/voices", "200",
                 {"total": n_voices, "limit": 100, "offset": 0, "data": voice_out})
    _set_example(spec, "/v1/providers", "200", [_provider_out(catalog, p) for p in providers])
    _set_example(spec, "/v1/providers/{provider_id}", "200", _provider_out(catalog, m0.provider_id))
    _set_example(spec, "/v1/providers/{provider_id}/models", "200",
                 {"total": sum(1 for r in _active_models(catalog) if r.provider_id == m0.provider_id),
                  "limit": 100, "offset": 0, "data": prov_models})
    _set_example(spec, "/v1/providers/{provider_id}/models/{model_id}", "200", model_out[0])
    _set_example(spec, "/v1/providers/{provider_id}/voices", "200",
                 {"total": sum(1 for r in catalog.voices if r.provider_id == v0.provider_id and r.voice.deprecated_at is None),
                  "limit": 100, "offset": 0, "data": prov_voices})
    _set_example(spec, "/v1/providers/{provider_id}/voices/{voice_id}", "200", voice_out[0])
    sample = _provider_out(catalog, m0.provider_id)
    sample["models"] = model_out[:1]
    sample["voices"] = []
    _set_example(spec, "/v1/catalog.json", "200",
                 {"schema_version": SCHEMA_VERSION, "etag": catalog.etag.strip('"'), "providers": [sample]})
    _set_example(spec, "/health", "200",
                 {"status": "ok", "providers": len(catalog.providers), "etag": catalog.etag.strip('"')})

    validation = {"detail": [{"type": "int_parsing", "loc": ["query", "limit"],
                              "msg": "Input should be a valid integer, unable to parse string as an integer",
                              "input": "abc"}]}
    for path, item in spec.get("paths", {}).items():
        if "422" in item.get("get", {}).get("responses", {}):
            _set_example(spec, path, "422", validation)

    # Path parameters default to real ids, so "Test Request" works without typing anything.
    for path in spec.get("paths", {}):
        if "{provider_id}" in path:
            pid = v0.provider_id if "voices" in path else m0.provider_id
            _set_param_example(spec, path, "provider_id", pid)
        if "{model_id}" in path:
            _set_param_example(spec, path, "model_id", m0.model.id)
        if "{voice_id}" in path:
            _set_param_example(spec, path, "voice_id", v0.voice.id)
    return spec
