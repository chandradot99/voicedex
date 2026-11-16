"""
Sync providers into the git-backed catalog (data/<provider>/*.json).

    uv run python scripts/sync.py deepgram              # dry-run: fetch, merge, show diff
    uv run python scripts/sync.py deepgram --write      # write data/deepgram/*.json
    uv run python scripts/sync.py --write               # all providers
    uv run python scripts/sync.py fishaudio --write --allow-shrink   # override the shrink guard

After --write, review with `git diff data/` and commit. The commit/PR is the review step;
deploying it publishes the data. See docs/design/v2-architecture.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from naaviq.catalog.files import DEFAULT_DATA_DIR, read_provider_dir, write_provider_dir  # noqa: E402
from naaviq.catalog.merge import GuardError, MergeReport, merge  # noqa: E402
from naaviq.sync.cache import _models_path, _voices_path  # noqa: E402
from naaviq.sync.registry import BY_ID, REGISTRY, load_syncer  # noqa: E402

_MAX_LISTED = 15


def _short(v, limit: int = 70) -> str:
    s = json.dumps(v, ensure_ascii=False, default=str) if not isinstance(v, str) else repr(v)
    return s if len(s) <= limit else s[: limit - 1] + "…"


def print_report(report: MergeReport, verbose: bool) -> None:
    counts = report.counts()
    if not counts:
        print("  No changes.")
        return
    for section in ("stt", "tts", "sts", "voices"):
        if section not in counts:
            continue
        c = counts[section]
        summary = "  ".join(f"{k} {c[k]}" for k in ("added", "updated", "revived", "deprecated") if c.get(k))
        print(f"  {section:7}: {summary}")
    limit = None if verbose else _MAX_LISTED
    for kind, sign in (("added", "+"), ("deprecated", "-"), ("revived", "↺"), ("updated", "~")):
        items = [c for c in report.changes if c.kind == kind]
        if not items:
            continue
        print(f"\n  {kind}:")
        for ch in items[:limit]:
            print(f"    {sign} [{ch.section}] {ch.key}")
            for f, (old, new) in ch.fields.items():
                print(f"        {f}: {_short(old)} → {_short(new)}")
        if limit and len(items) > limit:
            print(f"    … {len(items) - limit} more (use -v to list all)")


def clear_cache(provider_id: str) -> None:
    for p in (_models_path(provider_id, "stt"), _models_path(provider_id, "tts"),
              _models_path(provider_id, "sts"), _voices_path(provider_id)):
        p.unlink(missing_ok=True)


async def sync_one(provider_id: str, data_dir: Path, write: bool, allow_shrink: bool, verbose: bool) -> bool:
    print(f"\n{'─' * 60}\n  {provider_id}\n{'─' * 60}")
    entry = BY_ID[provider_id]
    print("  Fetching…", end="", flush=True)
    try:
        result = await load_syncer(provider_id).sync()
    except Exception as e:  # noqa: BLE001 — report any syncer failure and continue with the rest
        msg = str(e)
        print(f"\n  ✗ {type(e).__name__}: {msg.splitlines()[0] if msg else ''}")
        for line in msg.splitlines()[1:]:
            print(f"     {line.strip()}")
        return False
    print(" done")

    pdir = data_dir / provider_id
    current = read_provider_dir(pdir) if (pdir / "provider.json").exists() else None
    try:
        merged, report = merge(
            current, result,
            provider_id=provider_id, display_name=entry.display_name, seeded_type=entry.type,
            today=date.today(), allow_shrink=allow_shrink,
        )
    except GuardError as e:
        print(f"  ✗ Guard: {e}\n    Nothing written. Investigate, then re-run with --allow-shrink if it's real.")
        return False
    except ValueError as e:
        print(f"  ✗ Invalid data: {e}")
        return False

    print_report(report, verbose)
    if result.notes:
        print(f"\n  notes: {result.notes}")

    if write:
        write_provider_dir(pdir, merged)
        clear_cache(provider_id)
        print(f"\n  ✓ Wrote {pdir.relative_to(data_dir.parent)}/ — review with `git diff {pdir.relative_to(data_dir.parent)}`")
    else:
        print("\n  Dry-run — nothing written. Re-run with --write.")
    return True


async def main() -> int:
    ap = argparse.ArgumentParser(description="Sync providers into data/")
    ap.add_argument("providers", nargs="*", help="Provider IDs (default: all)")
    ap.add_argument("--write", action="store_true", help="Write data files (default: dry-run)")
    ap.add_argument("--allow-shrink", action="store_true", help="Bypass the mass-deprecation guard")
    ap.add_argument("-v", "--verbose", action="store_true", help="List every change")
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = ap.parse_args()

    unknown = [p for p in args.providers if p not in BY_ID]
    if unknown:
        print(f"Unknown providers: {', '.join(unknown)}\nAvailable: {', '.join(e.provider_id for e in REGISTRY)}")
        return 2

    ids = args.providers or [e.provider_id for e in REGISTRY]
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}   Data: {args.data_dir}")
    ok = 0
    for pid in ids:
        ok += await sync_one(pid, args.data_dir, args.write, args.allow_shrink, args.verbose)
    print(f"\n{'═' * 60}\n  {ok}/{len(ids)} providers synced")
    return 0 if ok == len(ids) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
