"""
Apply a framework-integration research file to every provider's provider.json.

A research pass (the framework's own docs: plugin lists, supported-provider pages) writes one JSON file per
framework:
    {"framework": "pipecat", "index_url": "https://docs.pipecat.ai/...",
     "providers": {"deepgram": {"types": ["stt", "tts"], "url": "https://...", "notes": "optional"}},
     "not_in_catalog": ["..."]}
The file is the complete list for that framework: listed providers get (or update) their entry, and providers
no longer listed lose it. Types are limited to the model types the provider actually has. Sync never touches
`integrations`.

    uv run python scripts/apply_integrations.py research/pipecat.json            # dry-run
    uv run python scripts/apply_integrations.py research/*.json --write
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from voicedex.catalog.files import read_provider_dir, write_provider_dir  # noqa: E402
from voicedex.catalog.schema import FRAMEWORKS, Integration  # noqa: E402


def apply(path: Path, data_dir: Path, write: bool, today: date) -> int:
    doc = json.loads(path.read_text())
    fw = doc.get("framework")
    if fw not in FRAMEWORKS:
        print(f"{path.name}: unknown framework {fw!r}")
        return 1
    listed: dict = doc.get("providers") or {}
    on_disk = {p.name for p in data_dir.iterdir() if (p / "provider.json").exists()}
    if unknown := sorted(set(listed) - on_disk):
        print(f"{fw}: UNKNOWN provider ids {unknown}")
        return 1
    added = updated = removed = 0
    for pid in sorted(on_disk):
        pdir = data_dir / pid
        pd = read_provider_dir(pdir)
        has = {str(getattr(m.type, "value", m.type)) for m in pd.models if m.deprecated_at is None}
        current = {i.framework: i for i in pd.provider.integrations}
        old = current.get(fw)
        new = None
        if pid in listed:
            row = listed[pid]
            types = [t for t in row.get("types", []) if t in has]
            if not types:
                print(f"  ! {fw}/{pid}: none of {row.get('types')} are types we list ({sorted(has)}); skipped")
            else:
                new = Integration(framework=fw, types=types, url=row["url"], notes=row.get("notes") or None,
                                  as_of=old.as_of if old and (old.types, old.url, old.notes) ==
                                  (types, row["url"], row.get("notes") or None) else today)
        if new == old:
            continue
        if new is None:
            current.pop(fw)
            removed += 1
            print(f"  - {pid}")
        else:
            current[fw] = new
            added += old is None
            updated += old is not None
            print(f"  {'+' if old is None else '~'} {pid}: {', '.join(new.types)}")
        pd.provider = pd.provider.model_copy(update={"integrations": list(current.values())})
        pd.provider = type(pd.provider).model_validate(pd.provider.model_dump())
        if write:
            write_provider_dir(pdir, pd)
    print(f"{fw}: {added} added, {updated} updated, {removed} removed"
          + ("" if write else " (dry-run)")
          + (f"; not in catalog: {', '.join(doc['not_in_catalog'])}" if doc.get("not_in_catalog") else ""))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = ap.parse_args()
    return max(apply(f, args.data_dir, args.write, date.today()) for f in args.files)


if __name__ == "__main__":
    raise SystemExit(main())
