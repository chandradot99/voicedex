"""
Voice-sample link check, run by scripts/sync.py on every voice list before merge.

Providers sometimes keep listing samples whose files are gone (Botnoi's S3 returns 403 for ~40% of its voices).
A sample is dropped only on a definitive answer — 401/403/404/410, or a 2xx HTML page instead of audio — never on a
timeout or 5xx, so a CDN hiccup can't erase samples. A dropped sample is recorded in `meta.preview_unavailable`
(the reason), which also tells merge not to restore the old URL. Spaces in URLs are percent-encoded.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from urllib.parse import quote, urlsplit, urlunsplit

import httpx

from voicedex.sync.base import SyncVoice

PER_HOST = 6
_DEAD = {401, 403, 404, 410}
_TIMEOUT = httpx.Timeout(20.0, connect=10.0)


def encode_url(url: str) -> str:
    """Percent-encode characters browsers would (spaces, non-ASCII) without touching existing escapes."""
    parts = urlsplit(url)
    return urlunsplit(parts._replace(path=quote(parts.path, safe="/%:@!$&'()*+,;=-._~")))


async def _status(client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str) -> str | None:
    """Reason the sample is dead, or None when it serves audio (or the answer isn't definitive)."""
    async with sem:
        for attempt in range(2):
            try:
                async with client.stream("GET", url, headers={"Range": "bytes=0-1023"}) as r:
                    if r.status_code in _DEAD:
                        return f"http {r.status_code}"
                    if r.status_code < 300 and r.headers.get("content-type", "").lower().startswith("text/html"):
                        return "html page, not audio"
                    return None
            except httpx.HTTPError:
                if attempt:
                    return None
                await asyncio.sleep(1)
    return None


async def drop_dead_previews(voices: list[SyncVoice]) -> int:
    """Encode URLs, check every sample, drop dead ones in place. Returns how many samples were dropped."""
    jobs: list[tuple[SyncVoice, int, str]] = []   # index -1 = preview_url, else previews[i]
    for v in voices:
        if v.preview_url:
            v.preview_url = encode_url(v.preview_url)
            jobs.append((v, -1, v.preview_url))
        for i, p in enumerate(v.previews):
            p["url"] = encode_url(p["url"])
            jobs.append((v, i, p["url"]))
    if not jobs:
        return 0
    sems: dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(PER_HOST))
    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0 (voicedex sample check)"}) as client:
        reasons = await asyncio.gather(*(_status(client, sems[urlsplit(u).netloc], u) for _, _, u in jobs))
    dead_extra: dict[int, set[int]] = defaultdict(set)
    dropped = 0
    for (v, i, _), reason in zip(jobs, reasons):
        if reason is None:
            continue
        dropped += 1
        v.meta = {**(v.meta or {}), "preview_unavailable": reason}
        if i < 0:
            v.preview_url = None
            v.preview_language = None
        else:
            dead_extra[id(v)].add(i)
    for v in voices:
        if id(v) in dead_extra:
            v.previews = [p for i, p in enumerate(v.previews) if i not in dead_extra[id(v)]]
    return dropped
