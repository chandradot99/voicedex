"""
Validate every file in data/ against the catalog schema and cross-record rules. Run in CI.

    uv run python scripts/validate.py              # validate
    uv run python scripts/validate.py --schema     # also regenerate schema/*.schema.json

Exit code 1 on any error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pydantic import ValidationError  # noqa: E402

from voicedex.catalog.files import DEFAULT_DATA_DIR, _dump, _record_json, read_provider_dir, sort_models, sort_voices  # noqa: E402
from voicedex.catalog.merge import derive_provider_type  # noqa: E402
from voicedex.catalog.schema import Model, Provider, Voice  # noqa: E402
from voicedex.sync.registry import BY_ID  # noqa: E402

SCHEMA_DIR = ROOT / "schema"


def write_json_schemas() -> None:
    SCHEMA_DIR.mkdir(exist_ok=True)
    for name, cls in (("provider", Provider), ("model", Model), ("voice", Voice)):
        (SCHEMA_DIR / f"{name}.schema.json").write_text(_dump(cls.model_json_schema()))


def check_provider(pdir: Path) -> list[str]:
    errs: list[str] = []
    try:
        pd = read_provider_dir(pdir)
    except (ValidationError, ValueError, json.JSONDecodeError) as e:
        return [f"{pdir.name}: {e}"]

    if pd.provider.id not in BY_ID:
        errs.append(f"{pdir.name}: not registered in voicedex/sync/registry.py")

    for kind, recs, key in (("model", pd.models, lambda r: (r.type, r.id)), ("voice", pd.voices, lambda r: r.id)):
        seen = set()
        for r in recs:
            k = key(r)
            if k in seen:
                errs.append(f"{pdir.name}: duplicate {kind} {k}")
            seen.add(k)

    for t in ("stt", "tts", "sts"):
        defaults = [m.id for m in pd.models if m.type == t and m.is_default and m.deprecated_at is None]
        if len(defaults) > 1:
            errs.append(f"{pdir.name}: multiple default {t} models {defaults}")

    ids_by_type = {t: {m.id for m in pd.models if m.type == t} for t in ("stt", "tts", "sts")}
    for m in pd.models:
        unknown = [r for r in m.replaces if r not in ids_by_type[m.type] or r == m.id]
        if unknown:
            errs.append(f"{pdir.name}: {m.type} model {m.id} replaces unknown models {unknown}")

    known_tts = {m.id for m in pd.models if m.type in ("tts", "sts")}
    for v in pd.voices:
        unknown = [c for c in v.compatible_models if c != "*" and c not in known_tts]
        if unknown:
            errs.append(f"{pdir.name}: voice {v.id} references unknown models {unknown}")
            break  # one example per provider is enough

    derived = derive_provider_type(pd.models)
    if derived and derived != pd.provider.type:
        errs.append(f"{pdir.name}: provider.type is {pd.provider.type!r} but active models say {derived!r}")

    # Files must be in canonical form, so diffs never contain formatting noise.
    canon = {
        "provider.json": _dump(_record_json(pd.provider)),
        "models.json": _dump([_record_json(m) for m in sort_models(pd.models)]),
        "voices.json": _dump([_record_json(v) for v in sort_voices(pd.voices)]),
    }
    for fname, text in canon.items():
        f = pdir / fname
        if f.exists() and f.read_text() != text:
            errs.append(f"{pdir.name}/{fname}: not in canonical form (run scripts/validate.py --fix)")
    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", action="store_true", help="Regenerate schema/*.schema.json")
    ap.add_argument("--fix", action="store_true",
                    help="Rewrite data files into canonical form (after schema normalization changes)")
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = ap.parse_args()

    if args.schema:
        write_json_schemas()
    if args.fix:
        from voicedex.catalog.files import write_provider_dir
        for pdir in sorted(p for p in args.data_dir.iterdir() if p.is_dir()):
            write_provider_dir(pdir, read_provider_dir(pdir))

    errors: list[str] = []
    dirs = sorted(p for p in args.data_dir.iterdir() if p.is_dir()) if args.data_dir.exists() else []
    for pdir in dirs:
        errors += check_provider(pdir)

    # Committed JSON Schema must match the code
    if not args.schema and SCHEMA_DIR.exists():
        for name, cls in (("provider", Provider), ("model", Model), ("voice", Voice)):
            f = SCHEMA_DIR / f"{name}.schema.json"
            if not f.exists() or f.read_text() != _dump(cls.model_json_schema()):
                errors.append(f"schema/{name}.schema.json is stale — run scripts/validate.py --schema")

    for e in errors:
        print(f"✗ {e}")
    print(f"{'✗' if errors else '✓'} {len(dirs)} providers checked, {len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
