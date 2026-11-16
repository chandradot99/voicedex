"""Read/write the data/<provider>/ JSON files deterministically (see design D1)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from naaviq.catalog.schema import Model, Provider, Voice

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@dataclass
class ProviderData:
    provider: Provider
    models: list[Model] = field(default_factory=list)
    voices: list[Voice] = field(default_factory=list)


def _dump(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _record_json(rec) -> dict:
    # Omit defaults/None so files stay compact and diffs show only meaningful values.
    return rec.model_dump(mode="json", exclude_defaults=True)


def sort_models(models: list[Model]) -> list[Model]:
    return sorted(models, key=lambda m: (m.type, m.id))


def sort_voices(voices: list[Voice]) -> list[Voice]:
    return sorted(voices, key=lambda v: v.id)


def read_provider_dir(path: Path) -> ProviderData:
    provider = Provider.model_validate_json((path / "provider.json").read_text())
    models_path, voices_path = path / "models.json", path / "voices.json"
    models = [Model.model_validate(m) for m in json.loads(models_path.read_text())] if models_path.exists() else []
    voices = [Voice.model_validate(v) for v in json.loads(voices_path.read_text())] if voices_path.exists() else []
    if provider.id != path.name:
        raise ValueError(f"{path}/provider.json has id {provider.id!r}; directory name must match")
    return ProviderData(provider, models, voices)


def write_provider_dir(path: Path, data: ProviderData) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "provider.json").write_text(_dump(_record_json(data.provider)))
    (path / "models.json").write_text(_dump([_record_json(m) for m in sort_models(data.models)]))
    (path / "voices.json").write_text(_dump([_record_json(v) for v in sort_voices(data.voices)]))


def read_all(data_dir: Path = DEFAULT_DATA_DIR) -> dict[str, ProviderData]:
    if not data_dir.exists():
        return {}
    out: dict[str, ProviderData] = {}
    for p in sorted(data_dir.iterdir()):
        if p.is_dir() and (p / "provider.json").exists():
            out[p.name] = read_provider_dir(p)
    return out
