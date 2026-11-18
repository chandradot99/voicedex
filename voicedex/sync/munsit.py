"""
Munsit (CNTXT AI) — Arabic speech-to-text and Faseeh text-to-speech.

Source: mixed.
  - Models: docs (docs.munsit.com; every page is also served as Markdown, full corpus at /llms-full.txt).
    `GET /api/v1/models` lists TTS model ids only (no languages, limits or prices), so the docs stay the source.
  - Voices: `GET /api/v1/voices/public` (x-api-key: MUNSIT_API_KEY) — Munsit's own catalogue only. The plain
    `/voices` endpoint mixes in the account's cloned voices, so it is never used; rows with `is_cloned` are
    dropped as a second guard. `sample_url` is a pre-signed S3 link that expires in an hour, so it is not stored.
    Without a key the sync stays docs-only and keeps the existing voices.
"""

from __future__ import annotations

import httpx

from voicedex.config import settings
from voicedex.sync.base import HTTP_TIMEOUT, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.docs_only import DocsOnlySyncer
from voicedex.sync.language import normalize_languages

VOICES_URL = "https://api.munsit.com/api/v1/voices/public"

# Munsit dialect ids → BCP-47 region for the language they belong to.
_ARABIC_DIALECTS = {
    "emirati": "ar-AE", "najdi": "ar-SA", "hijazi": "ar-SA", "southern_saudi": "ar-SA", "saudi": "ar-SA",
    "kuwaiti": "ar-KW", "qatari": "ar-QA", "omani": "ar-OM", "bahraini": "ar-BH", "egyptian": "ar-EG",
    "moroccan": "ar-MA",
}
_ENGLISH_ACCENTS = {
    "american": "en-US", "british": "en-GB", "australian": "en-AU", "indian": "en-IN", "ireland": "en-IE",
    "irish": "en-IE",
}


def _languages(langs: list[str], dialects: list[str]) -> list[str]:
    """Voice languages, regionalised by its dialects: an Emirati voice speaks ar-AE (+ plain en)."""
    out: list[str] = []
    for lang in langs:
        table = {"ar": _ARABIC_DIALECTS, "en": _ENGLISH_ACCENTS}.get(lang, {})
        regional = [table[d] for d in dialects if d in table]
        out += regional or [lang]
    return list(dict.fromkeys(normalize_languages(out)))


def parse_voices(rows: list[dict]) -> list[SyncVoice]:
    voices = []
    for r in rows:
        vid = str(r.get("voice_id") or "").strip()
        if not vid or r.get("is_cloned"):
            continue
        dialects = [d for d in (r.get("dialect") or []) if d]
        gender = (r.get("gender") or "").lower()
        voices.append(SyncVoice(
            voice_id=vid,
            display_name=(r.get("name") or vid).strip(),
            gender=gender if gender in ("male", "female") else None,
            category="premade",
            languages=_languages(r.get("languages") or [], dialects),
            description=r.get("description") or None,
            accent=dialects[0] if dialects else None,
            age=r.get("age") or None,
            use_cases=[t for t in (r.get("tags") or []) if t],
            compatible_models=["*"],
            meta={k: v for k, v in {"dialects": dialects, "type": r.get("type")}.items() if v},
        ))
    return voices


class MunsitSyncer(DocsOnlySyncer):
    provider_id = "munsit"
    source = "mixed"
    stt_docs = [
        "https://docs.munsit.com/speech-to-text/get-started.md",
        "https://docs.munsit.com/speech-to-text/transcribe.md",
        "https://docs.munsit.com/speech-to-text/streaming.md",
    ]
    tts_docs = [
        "https://docs.munsit.com/text-to-speech/models.md",
        "https://docs.munsit.com/text-to-speech/synthesize.md",
        "https://docs.munsit.com/reference/websocket.md",
    ]
    stt_guidance = (
        "Return every speech-to-text model id accepted in the `model` field of the batch and live streaming "
        "endpoints. Pricing is in credits: record the credit rate in pricing notes and set a USD price only "
        "where the docs publish one per unit (e.g. per hour of audio)."
    )
    tts_guidance = (
        "Return every text-to-speech model_id from the models page. Credit pricing goes in meta unless a "
        "per-character money price is published."
    )

    async def sync(self) -> SyncResult:
        result = await super().sync()
        if not settings.munsit_api_key:
            return result   # docs-only; merge keeps existing voices (empty section = unknown)
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await get_with_retry(client, VOICES_URL, headers={"x-api-key": settings.munsit_api_key})
            resp.raise_for_status()
            rows = resp.json()
        result.tts_voices = parse_voices(rows if isinstance(rows, list) else [])
        result.source = self.source
        result.api_urls = [VOICES_URL]
        result.notes = (f"docs: {len(result.stt_models)} STT, {len(result.tts_models)} TTS models; "
                        f"api: {len(result.tts_voices)} catalogue voices.")
        return result
