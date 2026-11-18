"""
Zyphra — ZONOS text-to-speech on Zyphra Cloud (OpenAI-compatible /api/v1/audio/speech).

Source: docs. Zyphra's public model list (https://api.zyphracloud.com/api/v1/models, no key needed) carries
each model's licence, Hugging Face link and price per 1M UTF-8 bytes; the zyphra.com model posts and the
Hugging Face model cards give languages and features.

Voices (mixed): `GET https://api.zyphracloud.com/api/v1/audio/default-voices` (Bearer ZYPHRA_API_KEY) —
Zyphra's stock voices only (cloned voices are a separate feature and never listed here). Without a key the
existing voices are kept.
"""

from __future__ import annotations

import httpx

from voicedex.config import settings
from voicedex.sync.base import HTTP_TIMEOUT, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.docs_only import DocsOnlySyncer
from voicedex.sync.language import accent_from_languages, normalize_languages

VOICES_URL = "https://api.zyphracloud.com/api/v1/audio/default-voices"


def parse_voices(rows: list[dict]) -> list[SyncVoice]:
    voices = []
    for r in rows:
        vid = str(r.get("voice_id") or "").strip()
        if not vid:
            continue
        langs = normalize_languages([r["language"]]) if r.get("language") else []
        gender = (r.get("gender") or "").lower()
        meta = {"name": r.get("name"), "sample_rate_hz": r.get("sample_rate_hz")}
        voices.append(SyncVoice(
            voice_id=vid,
            display_name=(r.get("display_name") or r.get("name") or vid).strip(),
            gender=gender if gender in ("male", "female") else None,
            category="premade",
            languages=langs,
            description=r.get("description") or None,
            accent=accent_from_languages(langs),
            compatible_models=["*"],
            meta={k: v for k, v in meta.items() if v is not None},
        ))
    return voices


class ZyphraSyncer(DocsOnlySyncer):
    provider_id = "zyphra"
    tts_docs = [
        "https://api.zyphracloud.com/api/v1/models",
        "https://www.zyphra.com/models",
        "https://www.zyphra.com/our-work/zonos3-mini",
        "https://www.zyphra.com/our-work/zonos2",
    ]
    tts_guidance = (
        "Return every TTS model in the Zyphra Cloud model list (type Audio, main use case TTS); model_id = its "
        "id. Price = audioPricePerMillionUtf8Bytes converted to a per-byte price_usd. open_weights from the "
        "licence and Hugging Face link. Languages from the model card; models no longer served are excluded."
    )

    async def sync(self) -> SyncResult:
        result = await super().sync()
        if not settings.zyphra_api_key:
            return result   # docs-only; merge keeps existing voices
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await get_with_retry(client, VOICES_URL,
                                        headers={"Authorization": f"Bearer {settings.zyphra_api_key}"})
            resp.raise_for_status()
            rows = resp.json()
        result.tts_voices = parse_voices(rows if isinstance(rows, list) else [])
        result.source = "mixed"
        result.api_urls = [VOICES_URL]
        result.notes = f"docs: {len(result.tts_models)} TTS models; api: {len(result.tts_voices)} default voices."
        return result
