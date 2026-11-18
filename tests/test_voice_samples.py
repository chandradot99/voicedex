"""Voice samples: per-language previews, the sample shown under a language filter, ElevenLabs URL pinning."""

import base64
import json
from urllib.parse import quote, unquote

from voicedex.catalog.schema import Voice
from voicedex.sync.elevenlabs import _sample_languages, _stable_preview
from voicedex.web.views import voice_sample


def _v(**kw) -> Voice:
    return Voice(id="v1", name="V", **kw)


def test_filter_picks_the_sample_in_that_language():
    v = _v(languages=["en-US", "zh-CN"], preview_url="https://x/en.mp3", preview_language="en-US",
           previews=[{"language": "zh-CN", "url": "https://x/zh.mp3"}])
    s = voice_sample(v, "zh")
    assert (s.url, s.language, s.matched) == ("https://x/zh.mp3", "zh-CN", True)
    assert voice_sample(v, None).url == "https://x/en.mp3"


def test_mismatch_is_flagged_with_the_sample_language():
    v = _v(languages=["en-US", "zh-CN"], preview_url="https://x/en.mp3", preview_language="en-US")
    s = voice_sample(v, "zh")
    assert s.matched is False and s.language == "en-US"


def test_monolingual_voice_sample_is_in_its_language_and_multilingual_unknown():
    assert voice_sample(_v(languages=["zh-CN", "zh-TW"], preview_url="https://x/a.mp3"), "zh").matched is True
    s = voice_sample(_v(languages=["*"], preview_url="https://x/a.mp3"), "zh")
    assert s.matched is False and s.language is None
    assert voice_sample(_v(languages=["zh"]), "zh") is None


def _payload(ts):
    raw = json.dumps({"voice_source": "premade", "filename": "a.mp3", "timestamp": ts}, separators=(",", ":"))
    return "https://api.example/v1/voices/X/previews/audio?payload=" + quote(base64.b64encode(raw.encode()).decode(), safe="")


def test_elevenlabs_preview_timestamp_is_pinned():
    a, b = _stable_preview(_payload(1794999600000000)), _stable_preview(_payload(1794996000000000))
    assert a == b
    data = json.loads(base64.b64decode(unquote(a.split("payload=")[1])))
    assert data == {"voice_source": "premade", "filename": "a.mp3", "timestamp": 0}
    assert _stable_preview("https://storage.example/a.mp3") == "https://storage.example/a.mp3"


def test_elevenlabs_verified_languages_become_previews():
    v = {"preview_url": "https://s/en.mp3"}
    verified = [
        {"locale": "en-US", "preview_url": "https://s/en.mp3"},
        {"locale": "en-US", "model_id": "other", "preview_url": "https://s/en.mp3"},
        {"locale": "cmn-CN", "preview_url": "https://s/zh.mp3"},
        {"language": "fr", "preview_url": None},
    ]
    out = _sample_languages(v, verified)
    assert out["preview_language"] == "en-US"
    assert out["previews"] == [{"language": "cmn-CN", "url": "https://s/zh.mp3"}]
    assert Voice(id="x", name="x", **out).previews[0].language == "zh-CN"
