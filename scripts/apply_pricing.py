"""
Apply docs-researched list prices to a provider's models in data/.

Reads .sync-cache/<provider>_pricing.json:
    [{"model_id": "...", "type": "stt|tts|sts", "pricing": {<Pricing>}}, ...]

Pricing lives on the model record; a later API sync never erases it (merge treats a missing price as
"unknown"), so prices for API-synced providers come from this docs pass. Changed models get
updated_at = today. Unknown model ids are reported, never created.

    uv run python scripts/apply_pricing.py deepgram            # dry-run
    uv run python scripts/apply_pricing.py deepgram --write
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from naaviq.catalog.files import read_provider_dir, write_provider_dir  # noqa: E402
from naaviq.catalog.schema import Pricing  # noqa: E402

CACHE = ROOT / ".sync-cache"


def apply(provider_id: str, data_dir: Path, write: bool) -> int:
    src = CACHE / f"{provider_id}_pricing.json"
    if not src.exists():
        print(f"{provider_id}: no {src.name}")
        return 1
    rows = json.loads(src.read_text())
    pdir = data_dir / provider_id
    pd = read_provider_dir(pdir)
    by_key = {(m.type.value if hasattr(m.type, "value") else m.type, m.id): m for m in pd.models}
    changed, unknown = [], []
    for row in rows:
        key = (row["type"], row["model_id"])
        model = by_key.get(key)
        if model is None:
            unknown.append(f"{key[0]}:{key[1]}")
            continue
        new = Pricing.model_validate(row["pricing"])
        if model.pricing != new:
            model.pricing = new
            model.updated_at = date.today()
            changed.append(f"{key[0]}:{key[1]}")
    print(f"{provider_id}: {len(changed)} priced/updated, {len(rows) - len(changed) - len(unknown)} unchanged"
          + (f", UNKNOWN ids: {unknown}" if unknown else ""))
    for c in changed:
        print(f"  ~ {c}")
    if write and changed:
        write_provider_dir(pdir, pd)
        src.unlink()
    elif write:
        src.unlink()
    return 1 if unknown else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("providers", nargs="+")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = ap.parse_args()
    rc = 0
    for p in args.providers:
        rc |= apply(p, args.data_dir, args.write)
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
