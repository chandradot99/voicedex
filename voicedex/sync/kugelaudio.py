"""
KugelAudio — text-to-speech (Kugel 3 family), speech-to-text (Kugel Ear) and speech-to-speech (Kugel Fluid).

Source: mixed.
  - Models: docs (docs.kugelaudio.com models / feature pages, indexed by docs.kugelaudio.com/llms.txt) and the
    pricing page (kugelaudio.com/pricing, EUR).
  - Voices: GET https://api.kugelaudio.com/v1/voices (Bearer KUGELAUDIO_API_KEY), paginated. The listing mixes
    the account's own voices with the public catalogue, so only `is_public` voices are kept. `sample_url` is a
    pre-signed link that expires in 15 minutes, so it is not stored. Without a key the existing voices are kept.
"""

from __future__ import annotations

import httpx

from voicedex.config import settings
from voicedex.sync.base import HTTP_TIMEOUT, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.docs_only import DocsOnlySyncer
from voicedex.sync.language import accent_from_languages, normalize_languages

VOICES_URL = "https://api.kugelaudio.com/v1/voices"
_PAGE = 100
_MAX_PAGES = 50


def parse_voices(rows: list[dict]) -> list[SyncVoice]:
    voices = []
    for r in rows:
        vid = str(r.get("voice_id") or r.get("id") or "").strip()
        if not vid or r.get("is_public") is not True:
            continue
        langs = normalize_languages([lang for lang in (r.get("supported_languages") or []) if lang])
        sex = (r.get("sex") or "").lower()
        meta = {"handle": r.get("handle"), "quality": r.get("quality"), "public_id": r.get("public_id")}
        voices.append(SyncVoice(
            voice_id=vid,
            display_name=(r.get("name") or vid).strip(),
            gender=sex if sex in ("male", "female") else None,
            category="premade",
            languages=langs,
            description=r.get("description") or None,
            accent=accent_from_languages(langs),
            age=r.get("age") or None,
            use_cases=[r["category"]] if r.get("category") else [],
            compatible_models=["*"],
            meta={k: v for k, v in meta.items() if v not in (None, "", vid)},
        ))
    return voices


class KugelAudioSyncer(DocsOnlySyncer):
    provider_id = "kugelaudio"
    source = "mixed"
    tts_docs = [
        "https://docs.kugelaudio.com/models.md",
        "https://docs.kugelaudio.com/api-reference/tts/audio-formats.md",
        "https://docs.kugelaudio.com/features/text-processing.md",
        "https://kugelaudio.com/pricing",
    ]
    stt_docs = [
        "https://docs.kugelaudio.com/models.md",
        "https://docs.kugelaudio.com/features/speech-to-text.md",
    ]
    sts_docs = [
        "https://docs.kugelaudio.com/models.md",
        "https://docs.kugelaudio.com/speech-to-speech/overview.md",
        "https://docs.kugelaudio.com/speech-to-speech/limits.md",
    ]
    tts_guidance = (
        "Return every current text-to-speech model id, plus legacy ids that carry their own published price "
        "(set meta.alias_of to the model they run on). Prices only from kugelaudio.com/pricing, in EUR "
        "(currency + price), per minute of generated audio. Languages from the supported-languages table."
    )
    stt_guidance = (
        "Return every speech-to-text model id with its listed languages, batch and streaming endpoints and "
        "per-request duration limit. Prices only if kugelaudio.com/pricing lists the model."
    )
    sts_guidance = (
        "Return every speech-to-speech (live voice agent) model id; lifecycle beta while the docs call the "
        "service a beta. Languages from the docs/changelog. Speech enhancement models are not STT/TTS — skip."
    )

    async def sync(self) -> SyncResult:
        result = await super().sync()
        if not settings.kugelaudio_api_key:
            return result   # docs-only; merge keeps existing voices
        headers = {"Authorization": f"Bearer {settings.kugelaudio_api_key}"}
        rows: list[dict] = []
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for page in range(_MAX_PAGES):
                resp = await get_with_retry(client, VOICES_URL, headers=headers,
                                            params={"limit": _PAGE, "offset": page * _PAGE})
                resp.raise_for_status()
                data = resp.json()
                batch = data.get("voices") or []
                rows += batch
                if not batch or len(rows) >= (data.get("total") or 0):
                    break
        result.tts_voices = parse_voices(rows)
        result.source = self.source
        result.api_urls = [VOICES_URL]
        result.notes = (f"docs: {len(result.stt_models)} STT, {len(result.tts_models)} TTS, "
                        f"{len(result.sts_models)} S2S models; api: {len(result.tts_voices)} public voices.")
        return result
