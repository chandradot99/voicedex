"""
Respeecher — two APIs: the Space API (realtime text-to-speech, one model per primary language) and the Voice
Marketplace API (speech-to-speech voice conversion plus text-to-speech, order based).

Source: docs (https://space.respeecher.com/docs/llms.txt; Markdown pages via ".md"; OpenAPI at /docs/openapi.json).
Space TTS models are the per-language base URLs (api.respeecher.com/v1/public/tts/<model>), served over Bytes
(HTTP), SSE and WebSocket. The Marketplace API (gateway.respeecher.com) has no model parameter: you upload or
synthesise a recording, then order conversions to a target voice (with an accent for STS, a narration style for
TTS), poll and download. Its voice conversion is recorded as an `sts` model (audio in, converted audio out; not
streaming) and its TTS as a separate non-streaming `tts` model. Prices: Space TTS from respeecher.com/real-time-tts-api,
Marketplace credits from respeecher.com/marketplace/pricing.

Voices (mixed):
  - Space: `GET https://api.respeecher.com/v1/public/tts/<model>/voices` (X-API-Key: RESPEECHER_API_KEY), one
    call per Space model; each voice belongs to the model it is listed under.
  - Marketplace: `GET https://gateway.respeecher.com/api/v2/voices` (api-key: RESPEECHER_MARKETPLACE_API_KEY).
    Only `public`, active and available voices are kept (never an account's private voices); account/owner ids,
    contact links and images are not stored. Every voice is a voice-conversion target (marketplace-sts); voices
    with narration styles also work with marketplace-tts.
Without a key, that section's existing voices are kept.
"""

from __future__ import annotations

import httpx

from voicedex.config import settings
from voicedex.sync.base import HTTP_TIMEOUT, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.docs_only import DocsOnlySyncer
from voicedex.sync.language import normalize_languages

SPACE_VOICES_URL = "https://api.respeecher.com/v1/public/tts/{model}/voices"
_ACCENTS = {"american": "en-US", "british": "en-GB", "australian": "en-AU", "irish": "en-IE", "scottish": "en-GB"}


MARKETPLACE_VOICES_URL = "https://gateway.respeecher.com/api/v2/voices"
# Marketplace accent locales → the English variety they produce. "no_ac" keeps the source speaker's accent.
_MARKETPLACE_ACCENTS = {"en_us": "en-US", "en_gb": "en-GB", "en_sc": "en-GB", "en_in": "en-IN"}


def parse_marketplace_voices(rows: list[dict]) -> list[SyncVoice]:
    voices = []
    for r in rows:
        vid = str(r.get("id") or "").strip()
        if not vid or r.get("visibility") != "public" or not r.get("active") or not r.get("available"):
            continue
        accents = [a.get("info") or {} for a in (r.get("accents") or [])]
        langs = sorted({_MARKETPLACE_ACCENTS[a["locale"]] for a in accents if a.get("locale") in _MARKETPLACE_ACCENTS})
        styles = [t["name"] for st in (r.get("narration_styles") or []) for t in (st.get("tags") or []) if t.get("name")]
        gender = (r.get("gender") or "").lower()
        meta = {
            "accents": [a["name"] for a in accents if a.get("name")] or None,
            "category": r.get("category"),
            "voice_talent": r.get("voice_talent"),
            "cost_multiplier": r.get("cost_multiplier"),
            "pitch_group": r.get("pitch_group"),
            "slug": r.get("slug"),
        }
        voices.append(SyncVoice(
            voice_id=vid,
            display_name=(r.get("name") or vid).strip(),
            gender=gender if gender in ("male", "female") else None,
            category="premade",
            languages=normalize_languages(langs),
            age=r.get("age_group") or None,
            tags=list(dict.fromkeys(s.lower() for s in styles)),
            compatible_models=["marketplace-sts"] + (["marketplace-tts"] if styles else []),
            meta={k: v for k, v in meta.items() if v not in (None, "")},
        ))
    return voices


def parse_space_voices(model_id: str, languages: list[str], rows: list[dict]) -> list[SyncVoice]:
    """One Space model's voice list. The model's languages apply; an English accent narrows en → en-XX."""
    voices = []
    for r in rows:
        vid = str(r.get("id") or "").strip()
        if not vid:
            continue
        full = (r.get("full_name") or vid).strip()
        style = full.split(":", 1)[1].strip() if ":" in full else None
        accent = (r.get("accent") or "").strip().lower() or None
        langs = [_ACCENTS[accent]] if accent in _ACCENTS and languages == ["en"] else languages
        gender = (r.get("gender") or "").lower()
        meta = {"recommended": True if r.get("is_best") else None,
                "experimental": True if r.get("experimental") else None}
        voices.append(SyncVoice(
            voice_id=vid,
            display_name=full,
            gender=gender if gender in ("male", "female") else None,
            category="premade",
            languages=normalize_languages(langs),
            accent=accent,
            age=(r.get("age") or None),
            tags=[style.lower()] if style else [],
            compatible_models=[model_id],
            meta={k: v for k, v in meta.items() if v is not None},
        ))
    return voices

_DOCS = "https://space.respeecher.com/docs/"


class RespeecherSyncer(DocsOnlySyncer):
    provider_id = "respeecher"
    tts_docs = [
        _DOCS + "llms.txt",
        _DOCS + "choosing-an-api.md",
        _DOCS + "space/models-and-languages.md",
        _DOCS + "space/limits.md",
        _DOCS + "space/api/tts/bytes.md",
        _DOCS + "space/api/tts/sse.md",
        _DOCS + "marketplace/api-overview.md",
        "https://www.respeecher.com/real-time-tts-api",
        "https://www.respeecher.com/marketplace/pricing",
    ]
    sts_docs = [
        _DOCS + "choosing-an-api.md",
        _DOCS + "marketplace/api-overview.md",
        "https://www.respeecher.com/marketplace/pricing",
    ]
    tts_guidance = (
        "Return one model per Space API base-URL model in the Models & Languages table (model_id = the path "
        "segment), with its primary language, output encodings, sample rate and per-request limit; mark the "
        "model the docs call the SDK default as default. Also return one non-streaming model for Marketplace "
        "API text-to-speech. Prices only as published per character by Respeecher."
    )
    sts_guidance = (
        "Return one model for Marketplace API speech-to-speech voice conversion (order-based, not streaming), "
        "with accepted input formats and the published per-minute credit price."
    )

    async def sync(self) -> SyncResult:
        result = await super().sync()
        space_key, market_key = settings.respeecher_api_key, settings.respeecher_marketplace_api_key
        if not space_key or not market_key:
            return result   # partial keys would shrink the other section; keep existing voices
        space = [m for m in result.tts_models if m.model_id != "marketplace-tts" and m.streaming]
        voices: list[SyncVoice] = []
        urls: list[str] = []
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for m in space:
                url = SPACE_VOICES_URL.format(model=m.model_id)
                resp = await get_with_retry(client, url, headers={"X-API-Key": space_key})
                resp.raise_for_status()
                rows = resp.json()
                voices += parse_space_voices(m.model_id, m.languages, rows if isinstance(rows, list) else [])
                urls.append(url)
            market_rows: list[dict] = []
            for page in range(50):
                resp = await get_with_retry(client, MARKETPLACE_VOICES_URL, headers={"api-key": market_key},
                                            params={"limit": 100, "offset": page * 100})
                resp.raise_for_status()
                batch = resp.json().get("list") or []
                market_rows += batch
                if len(batch) < 100:
                    break
            urls.append(MARKETPLACE_VOICES_URL)
        market = parse_marketplace_voices(market_rows)
        result.tts_voices = voices + market
        result.source = "mixed"
        result.api_urls = urls
        result.notes = (f"docs: {len(result.tts_models)} TTS, {len(result.sts_models)} S2S models; api: "
                        f"{len(voices)} Space + {len(market)} Marketplace voices.")
        return result
