"""
Check that every active voice sample URL in data/ still serves audio.

    uv run python scripts/check_previews.py                 # all providers, summary per provider
    uv run python scripts/check_previews.py fishaudio -v    # one provider, list broken URLs
    uv run python scripts/check_previews.py --json out.json # machine-readable result

A sample is OK when a ranged GET returns 2xx with an audio/* or octet-stream body (or a body whose first bytes
look like audio). Requests are capped per host so no provider's CDN is hammered.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from voicedex.catalog.files import read_provider_dir  # noqa: E402

PER_HOST = 6
TIMEOUT = httpx.Timeout(20.0, connect=10.0)
_MAGIC = (b"ID3", b"RIFF", b"OggS", b"fLaC", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"\x1aE\xdf\xa3")


def _looks_audio(ctype: str, head: bytes) -> bool:
    if ctype.startswith(("audio/", "video/")) or "octet-stream" in ctype:
        return True
    return head.startswith(_MAGIC) or head[4:8] == b"ftyp"


async def _check(client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str) -> str:
    async with sem:
        for attempt in range(2):
            try:
                async with client.stream("GET", url, headers={"Range": "bytes=0-2047"}) as r:
                    head = b""
                    async for chunk in r.aiter_bytes():
                        head += chunk
                        if len(head) >= 16:
                            break
                    if r.status_code >= 400:
                        return f"http {r.status_code}"
                    ctype = r.headers.get("content-type", "").lower()
                    return "ok" if _looks_audio(ctype, head) else f"not audio ({ctype or 'no type'})"
            except httpx.HTTPError as e:
                if attempt:
                    return f"error {type(e).__name__}"
                await asyncio.sleep(1)
    return "error"


def collect(providers: list[str]) -> list[tuple[str, str, str]]:
    rows = []
    for pdir in sorted((ROOT / "data").iterdir()):
        if providers and pdir.name not in providers:
            continue
        if not (pdir / "voices.json").exists():
            continue
        for v in read_provider_dir(pdir).voices:
            if v.deprecated_at is not None:
                continue
            urls = ([v.preview_url] if v.preview_url else []) + [p.url for p in v.previews]
            rows += [(pdir.name, v.id, u) for u in urls]
    return rows


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("providers", nargs="*")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--json")
    args = ap.parse_args()
    rows = collect(args.providers)
    sems: dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(PER_HOST))
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0 (voicedex preview check)"}) as client:
        results = await asyncio.gather(*(_check(client, sems[urlparse(u).netloc], u) for _, _, u in rows))
    by = defaultdict(Counter)
    for (pid, _, _), res in zip(rows, results):
        by[pid]["ok" if res == "ok" else res] += 1
    bad = 0
    for pid, c in sorted(by.items()):
        n_bad = sum(n for k, n in c.items() if k != "ok")
        bad += n_bad
        if n_bad:
            print(f"{pid:22} {c['ok']:5} ok  {n_bad:5} broken  {dict((k, n) for k, n in c.items() if k != 'ok')}")
    print(f"\n{len(rows)} samples checked, {bad} broken across {sum(1 for c in by.values() if len(c) > 1 or 'ok' not in c)} providers.")
    if args.verbose:
        for (pid, vid, url), res in zip(rows, results):
            if res != "ok":
                print(f"  {pid} {vid}: {res}  {url}")
    if args.json:
        Path(args.json).write_text(json.dumps([{"provider": p, "voice": v, "url": u, "result": r}
                                               for (p, v, u), r in zip(rows, results)], indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
