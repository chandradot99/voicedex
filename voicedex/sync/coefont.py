"""
CoeFont — Japanese AI voice platform; CoeFont API v2 text-to-speech.

Source: mixed.
  - Model: docs (docs.coefont.cloud ReDoc reference, coefont.cloud/llms.txt for plans). The API has no model
    parameter: POST /v2/text2speech takes a CoeFont (voice) uuid, so the catalog records one TTS model.
    The API requires the Plus plan; no per-character API price is published.
  - Voices: GET https://backend.coefont.cloud/coefonts/pro — the keyless list behind coefont.cloud/search's
    "CoeFont Pro" tab (the same set the signed API's GET /v2/coefonts/pro returns). Only voices flagged
    `public` and `pro` are kept. Creator account fields (userId, screenName) and free-text descriptions (which
    carry creators' social links) are never stored.
"""

from __future__ import annotations

import httpx

from voicedex.sync.base import HTTP_TIMEOUT, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.docs_only import DocsOnlySyncer
from voicedex.sync.language import normalize_languages

VOICES_URL = "https://backend.coefont.cloud/coefonts/pro"

# CoeFont's own Japanese gender tags.
_GENDER_TAGS = {"女性": "female", "男性": "male"}


def parse_voices(rows: list[dict]) -> list[SyncVoice]:
    voices = []
    for r in rows:
        vid = str(r.get("coefontId") or "").strip()
        if not vid or not r.get("public") or not r.get("pro"):
            continue
        tags = [t for t in (r.get("tags") or []) if t]
        genders = {_GENDER_TAGS[t] for t in tags if t in _GENDER_TAGS}
        meta = {
            "caption": r.get("caption") or None,
            "plan": r.get("plan") or None,
            "engine_version": r.get("version"),
            "official": r.get("official"),
        }
        voices.append(SyncVoice(
            voice_id=vid,
            display_name=(r.get("name") or vid).strip(),
            gender=genders.pop() if len(genders) == 1 else None,
            category="premade",
            languages=normalize_languages([r["lang"]]) if r.get("lang") else [],
            tags=[t for t in tags if t not in _GENDER_TAGS],
            compatible_models=["*"],
            meta={k: v for k, v in meta.items() if v is not None},
        ))
    return voices


class CoeFontSyncer(DocsOnlySyncer):
    provider_id = "coefont"
    source = "mixed"
    tts_docs = [
        "https://docs.coefont.cloud/en/",
        "https://coefont.cloud/llms.txt",
    ]
    tts_guidance = (
        "The API has no model id; return one TTS model for the text2speech endpoint with its documented "
        "text limit, formats and parameters. Pricing only if a per-unit API price is published."
    )

    async def sync(self) -> SyncResult:
        result = await super().sync()
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await get_with_retry(client, VOICES_URL)
            resp.raise_for_status()
            rows = resp.json()
        result.tts_voices = parse_voices(rows if isinstance(rows, list) else [])
        result.source = self.source
        result.api_urls = [VOICES_URL]
        result.notes = f"docs: {len(result.tts_models)} TTS model; api: {len(result.tts_voices)} Pro voices."
        return result
