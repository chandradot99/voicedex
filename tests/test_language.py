"""Tests for BCP-47 language normalization."""

import pytest

from naaviq.sync.language import normalize_language, normalize_languages


@pytest.mark.parametrize(
    "raw, expected",
    [
        # Region gets uppercased
        ("en-us", "en-US"),
        ("fr-fr", "fr-FR"),
        ("hi-in", "hi-IN"),
        # Already uppercase — idempotent
        ("en-US", "en-US"),
        ("hi-IN", "hi-IN"),
        # Bare language code — lowercased
        ("en", "en"),
        ("EN", "en"),
        # Wildcard passes through
        ("*", "*"),
        # Underscore separator normalized to hyphen
        ("en_US", "en-US"),
        ("zh_hans", "zh-Hans"),
        # Script subtag (4 letters) → title-case
        ("zh-hans", "zh-Hans"),
        ("zh-Hans", "zh-Hans"),
        # Three parts: language-script-region
        ("zh-Hant-TW", "zh-Hant-TW"),
        ("zh-hant-tw", "zh-Hant-TW"),
        # Empty string is preserved (caller may want to filter later)
        ("", ""),
    ],
)
def test_normalize_language(raw: str, expected: str) -> None:
    assert normalize_language(raw) == expected


def test_normalize_languages_preserves_order_and_count() -> None:
    out = normalize_languages(["en-us", "fr-fr", "hi-IN", "*"])
    assert out == ["en-US", "fr-FR", "hi-IN", "*"]


def test_normalize_languages_empty_list() -> None:
    assert normalize_languages([]) == []


@pytest.mark.parametrize("raw, expected", [
    ("cmn-CN", "zh-CN"), ("eng", "en"), ("zho", "zh"), ("deu-DE", "de-DE"),
    ("yue-HK", "yue-HK"), ("fil-PH", "fil-PH"), ("es-419", "es-419"), (" en-us ", "en-US"),
])
def test_iso639_3_collapses_to_shortest_code(raw, expected):
    assert normalize_language(raw) == expected


async def test_get_with_retry_honours_retry_after(monkeypatch):
    import asyncio

    import httpx

    from naaviq.sync.base import get_with_retry

    calls, slept = [], []
    responses = [httpx.Response(429, headers={"Retry-After": "3"}), httpx.Response(503), httpx.Response(200)]

    async def fake_sleep(s):
        slept.append(s)

    def handler(request):
        calls.append(request.url)
        return responses[len(calls) - 1]

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
        r = await get_with_retry(c, "https://x.test/")
    assert r.status_code == 200 and len(calls) == 3 and slept == [3.0, 2.0]
