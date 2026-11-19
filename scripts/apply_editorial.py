"""
Apply researched editorial fields to data/<provider>/provider.json.

Editorial fields (website, description, access, headquarters, regions, compliance, links) are hand-curated;
sync never touches them. A research pass writes them to .sync-cache/<provider>_editorial.json:

    {"website": "https://...", "description": "...", "access": "self_serve", "headquarters": "IN",
     "regions": ["asia"], "compliance": ["soc2"], "links": {"docs": "...", "pricing": "..."}}

Only keys present in the file are set. Validated against the schema before writing.

    uv run python scripts/apply_editorial.py upliftai            # dry-run
    uv run python scripts/apply_editorial.py upliftai --write    # write + delete the cache file
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from voicedex.catalog.files import read_provider_dir, write_provider_dir  # noqa: E402
from voicedex.catalog.schema import Provider  # noqa: E402

CACHE = ROOT / ".sync-cache"
FIELDS = {"website", "description", "access", "headquarters", "regions", "compliance", "links", "verified"}


def apply(provider_id: str, data_dir: Path, write: bool) -> int:
    src = CACHE / f"{provider_id}_editorial.json"
    if not src.exists():
        print(f"{provider_id}: no {src.name}")
        return 1
    patch = json.loads(src.read_text())
    unknown = set(patch) - FIELDS
    if unknown:
        print(f"{provider_id}: unknown editorial keys {sorted(unknown)}")
        return 1
    pdir = data_dir / provider_id
    pd = read_provider_dir(pdir)
    before = pd.provider.model_dump(mode="json")
    merged = {**before, **patch}
    if "links" in patch:
        merged["links"] = {**before.get("links", {}), **patch["links"]}
    pd.provider = Provider.model_validate(merged)
    after = pd.provider.model_dump(mode="json")
    changed = {k: after[k] for k in after if after[k] != before.get(k)}
    for k, v in changed.items():
        print(f"  {provider_id}.{k}: {json.dumps(v, ensure_ascii=False)[:160]}")
    if write:
        write_provider_dir(pdir, pd)
        src.unlink()
        print(f"{provider_id}: wrote {len(changed)} field(s)")
    else:
        print(f"{provider_id}: dry-run, {len(changed)} field(s) would change")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("providers", nargs="+")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = ap.parse_args()
    return max(apply(p, args.data_dir, args.write) for p in args.providers)


if __name__ == "__main__":
    raise SystemExit(main())
