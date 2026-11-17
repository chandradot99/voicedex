"""
Apply docs-researched fields (pricing, capabilities) to a provider's models in data/.

For API-synced providers whose API doesn't expose prices or feature support, a docs pass fills them
in. A later API sync never erases them: merge treats missing pricing / empty capabilities as
"unknown" and keeps the existing value.

Reads .sync-cache/<provider>_docs.json (and the older <provider>_pricing.json):
    [{"model_id": "...", "type": "stt|tts|sts",
      "pricing": {<Pricing>},                      # optional
      "capabilities": ["speaker_diarization", ...],  # optional, controlled vocabulary
      "capability_notes": {"term": "caveat"},      # optional → meta.capability_notes
      "source_urls": ["https://..."]}]             # optional → meta.docs_sources

Changed models get updated_at = today. Unknown model ids are reported, never created.

    uv run python scripts/apply_docs.py deepgram            # dry-run
    uv run python scripts/apply_docs.py deepgram --write
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
from voicedex.catalog.schema import MODEL_CAPABILITIES, TTS_CAPABILITIES, Pricing  # noqa: E402

CACHE = ROOT / ".sync-cache"


def _sources(provider_id: str) -> list[Path]:
    return [p for p in (CACHE / f"{provider_id}_docs.json", CACHE / f"{provider_id}_pricing.json") if p.exists()]


def apply(provider_id: str, data_dir: Path, write: bool) -> int:
    srcs = _sources(provider_id)
    if not srcs:
        print(f"{provider_id}: no {provider_id}_docs.json / _pricing.json in .sync-cache")
        return 1
    rows = [row for src in srcs for row in json.loads(src.read_text())]
    pdir = data_dir / provider_id
    pd = read_provider_dir(pdir)
    by_key = {(str(getattr(m.type, "value", m.type)), m.id): m for m in pd.models}
    changed: list[str] = []
    unknown: list[str] = []
    rc = 0
    for row in rows:
        key = (row["type"], row["model_id"])
        model = by_key.get(key)
        if model is None:
            unknown.append(f"{key[0]}:{key[1]}")
            continue
        before = model.model_dump(mode="json")
        if row.get("pricing"):
            model.pricing = Pricing.model_validate(row["pricing"])
        if row.get("capabilities"):
            bad = [c for c in row["capabilities"] if c not in MODEL_CAPABILITIES]
            wrong = [c for c in row["capabilities"] if (c in TTS_CAPABILITIES) != (key[0] == "tts")]
            if bad or wrong:
                print(f"  ✗ {key[0]}:{key[1]}: unknown {bad} / wrong-modality {wrong} capabilities")
                rc = 1
                continue
            model.capabilities = sorted(set(row["capabilities"]))
            if row.get("capability_notes"):
                model.meta = {**model.meta, "capability_notes": row["capability_notes"]}
        if row.get("source_urls"):
            model.meta = {**model.meta, "docs_sources": row["source_urls"]}
        if model.model_dump(mode="json") != before:
            model.updated_at = date.today()
            changed.append(f"{key[0]}:{key[1]}")
    print(f"{provider_id}: {len(changed)} updated, {len(rows) - len(changed) - len(unknown)} unchanged"
          + (f", UNKNOWN ids: {unknown}" if unknown else ""))
    for c in changed:
        print(f"  ~ {c}")
    if write and rc == 0:
        if changed:
            write_provider_dir(pdir, pd)
        for src in srcs:
            src.unlink()
    return 1 if (unknown or rc) else 0


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
