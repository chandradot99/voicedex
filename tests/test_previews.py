"""Dead voice-sample links are dropped on definitive answers only, and merge doesn't restore them."""

import asyncio
from datetime import date

import httpx

from voicedex.catalog.merge import merge
from voicedex.sync import previews
from voicedex.sync.base import SyncResult, SyncVoice


def _run(voices, routes, monkeypatch):
    def handler(req: httpx.Request) -> httpx.Response:
        status, ctype = routes[str(req.url)]
        if status == "timeout":
            raise httpx.ConnectTimeout("slow", request=req)
        return httpx.Response(status, headers={"content-type": ctype}, content=b"ID3....")

    real = httpx.AsyncClient
    monkeypatch.setattr(previews.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    real_sleep = asyncio.sleep
    monkeypatch.setattr(previews.asyncio, "sleep", lambda *_: real_sleep(0))
    return asyncio.run(previews.drop_dead_previews(voices))


def test_only_definitive_failures_are_dropped(monkeypatch):
    a = SyncVoice("a", "A", preview_url="https://s/a b.wav", preview_language="th")
    b = SyncVoice("b", "B", preview_url="https://s/b.mp3",
                  previews=[{"language": "zh", "url": "https://s/zh.mp3"}, {"language": "fr", "url": "https://s/fr.mp3"}])
    c = SyncVoice("c", "C", preview_url="https://s/c.mp3")
    routes = {"https://s/a%20b.wav": (403, "application/xml"), "https://s/b.mp3": (206, "audio/mpeg"),
              "https://s/zh.mp3": (200, "text/html"), "https://s/fr.mp3": (503, "text/plain"),
              "https://s/c.mp3": ("timeout", "")}
    assert _run([a, b, c], routes, monkeypatch) == 2
    assert a.preview_url is None and a.preview_language is None and a.meta["preview_unavailable"] == "http 403"
    assert b.preview_url == "https://s/b.mp3" and [p["language"] for p in b.previews] == ["fr"]
    assert c.preview_url == "https://s/c.mp3" and "preview_unavailable" not in c.meta


def test_merge_does_not_restore_a_dead_sample():
    old = SyncResult(stt_models=[], tts_models=[], tts_voices=[SyncVoice("a", "A", preview_url="https://s/a.wav")],
                     source="api")
    pd, _ = merge(None, old, provider_id="acme", display_name="Acme", seeded_type="tts", today=date(2026, 11, 1))
    gone = SyncVoice("a", "A", meta={"preview_unavailable": "http 403"})
    new = SyncResult(stt_models=[], tts_models=[], tts_voices=[gone], source="api")
    pd2, _ = merge(pd, new, provider_id="acme", display_name="Acme", seeded_type="tts", today=date(2026, 11, 2))
    assert pd2.voices[0].preview_url is None
    unknown = SyncResult(stt_models=[], tts_models=[], tts_voices=[SyncVoice("a", "A")], source="api")
    pd3, _ = merge(pd, unknown, provider_id="acme", display_name="Acme", seeded_type="tts", today=date(2026, 11, 2))
    assert pd3.voices[0].preview_url == "https://s/a.wav"   # plain None still means "unknown"
