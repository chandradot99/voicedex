"""
Sync providers into the git-backed catalog (data/<provider>/*.json).

    uv run python scripts/sync.py deepgram              # dry-run: fetch, merge, show diff
    uv run python scripts/sync.py deepgram --write      # write data/deepgram/*.json
    uv run python scripts/sync.py --write               # all providers
    uv run python scripts/sync.py fishaudio --write --allow-shrink   # override the shrink guard
    uv run python scripts/sync.py --reuse-docs --write              # refresh API data for all providers;
                                                                    # docs-extracted records reused from data/

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

from voicedex.catalog.files import DEFAULT_DATA_DIR, read_provider_dir, write_provider_dir  # noqa: E402
from voicedex.catalog.merge import GuardError, MergeReport, merge  # noqa: E402
from voicedex.sync.cache import _models_path, _voices_path  # noqa: E402
from voicedex.sync.registry import BY_ID, REGISTRY, load_syncer  # noqa: E402

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


def _model_to_cache(m) -> dict:
    """Inverse of merge.model_from_sync, in the .sync-cache SyncModel JSON shape."""
    d = m.model_dump(mode="json", exclude_none=True)
    meta = dict(d.pop("meta", {}))
    for src, dst in (("family", "parent_model_id"), ("snapshot_date", "snapshot_date"),
                     ("alias_of", "alias_of"), ("batch", "batch")):
        if src in d:
            meta[dst] = d.pop(src)
    for k in ("first_seen", "updated_at", "deprecated_at", "provenance"):
        d.pop(k, None)
    d["model_id"] = d.pop("id")
    d["display_name"] = d.pop("name")
    d["meta"] = meta
    d["source"] = "docs"
    return d


def seed_cache_from_data(provider_id: str, data_dir: Path) -> list[str]:
    """--reuse-docs: re-use the already-reviewed docs-extracted records in data/ instead of
    re-reading the docs, so an API-side refresh (e.g. new voices) doesn't force a docs pass.
    Never overwrites a cache file that already exists (a fresh extraction always wins)."""
    pdir = data_dir / provider_id
    if not (pdir / "provider.json").exists():
        return []
    pd = read_provider_dir(pdir)
    seeded = []
    for t in ("stt", "tts", "sts"):
        recs = [m for m in pd.models if m.type == t and m.deprecated_at is None
                and m.provenance is not None and m.provenance.method == "docs"]
        path = _models_path(provider_id, t)
        if recs and not path.exists():
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps([_model_to_cache(m) for m in recs], indent=2))
            seeded.append(f"{t} models ({len(recs)})")
    vs = pd.provider.voices_source
    if vs is not None and vs.method == "docs" and not _voices_path(provider_id).exists():
        voices = [v for v in pd.voices if v.deprecated_at is None]
        rows = []
        for v in voices:
            d = v.model_dump(mode="json", exclude_none=True)
            for k in ("first_seen", "updated_at", "deprecated_at"):
                d.pop(k, None)
            d["voice_id"] = d.pop("id")
            d["display_name"] = d.pop("name")
            rows.append(d)
        _voices_path(provider_id).parent.mkdir(exist_ok=True)
        _voices_path(provider_id).write_text(json.dumps(rows, indent=2))
        seeded.append(f"voices ({len(rows)})")
    return seeded


def clear_cache(provider_id: str) -> None:
    for p in (_models_path(provider_id, "stt"), _models_path(provider_id, "tts"),
              _models_path(provider_id, "sts"), _voices_path(provider_id)):
        p.unlink(missing_ok=True)


async def sync_one(provider_id: str, data_dir: Path, write: bool, allow_shrink: bool, verbose: bool,
                   reuse_docs: bool = False) -> bool:
    print(f"\n{'─' * 60}\n  {provider_id}\n{'─' * 60}")
    entry = BY_ID[provider_id]
    seeded = seed_cache_from_data(provider_id, data_dir) if reuse_docs else []
    if seeded:
        print(f"  Reusing reviewed docs data from data/: {', '.join(seeded)}")
    try:
        return await _sync_one(provider_id, entry, data_dir, write, allow_shrink, verbose)
    finally:
        if seeded:
            clear_cache(provider_id)  # seeded copies must never masquerade as a fresh extraction


async def _sync_one(provider_id: str, entry, data_dir: Path, write: bool, allow_shrink: bool, verbose: bool) -> bool:
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
    ap.add_argument("--reuse-docs", action="store_true",
                    help="Refresh API data only; reuse docs-extracted records already in data/")
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    args = ap.parse_args()

    unknown = [p for p in args.providers if p not in BY_ID]
    if unknown:
        print(f"Unknown providers: {', '.join(unknown)}\nAvailable: {', '.join(e.provider_id for e in REGISTRY)}")
        return 2

    retired = [p for p in args.providers if BY_ID[p].retired]
    for p in retired:
        print(f"Skipping {p}: retired (see data/{p}/provider.json)")
    ids = [p for p in args.providers if p not in retired] if args.providers \
        else [e.provider_id for e in REGISTRY if not e.retired]
    if not ids:
        return 0
    print(f"Mode: {'WRITE' if args.write else 'DRY-RUN'}   Data: {args.data_dir}")
    failed = [pid for pid in ids
              if not await sync_one(pid, args.data_dir, args.write, args.allow_shrink, args.verbose, args.reuse_docs)]
    print(f"\n{'═' * 60}\n  {len(ids) - len(failed)}/{len(ids)} providers synced")
    if failed:
        print(f"  ✗ FAILED: {', '.join(failed)} — see the errors above")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
