"""
Speechify sync script.

Source: mixed
  - TTS voices: GET https://api.speechify.ai/v1/voices (no pagination, auth required)
  - TTS models: AI-parsed from docs (Simba model family)
  - STT: not offered — stt_models=[]

Voice object shape:
  {
    "id": "henry",
    "display_name": "Henry",
    "gender": "male",          -- "male" | "female" | "notSpecified"
    "locale": "en-US",
    "type": "shared",          -- "shared" | "personal" — only "shared" voices included
    "models": [{"model": "simba-english", "supported_locales": ["en-US"]}],
    "avatar_image": "...",
    "preview_audio": "...",
    "tags": ["narration"]
  }

Auth: Authorization: Bearer header
Config: SPEECHIFY_API_KEY
"""

from __future__ import annotations

import asyncio

import httpx

from voicedex.config import settings
from voicedex.sync.ai_parser import parse_models_from_docs
from voicedex.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncResult, SyncVoice
from voicedex.sync.language import normalize_languages

_BASE_URL = "https://api.speechify.ai/v1"
_VOICES_URL = f"{_BASE_URL}/voices"

_DOCS_URLS = [
    "https://docs.speechify.ai/build/guides/concepts/models",
    "https://docs.speechify.ai/build/guides/text-to-speech/language-support",
    "https://speechify.ai/pricing",
]

_TTS_MODEL_GUIDANCE = (
    "Return every Simba TTS model id the API accepts. Legacy models with a published shutdown date "
    "stay in with eol_date and meta.replacement; exclude retired ones. is_default=true for the model "
    "the docs recommend for new code (record the API's fallback model in meta if different)."
)

_GENDER_MAP = {"male": "male", "female": "female", "notspecified": "neutral"}


class SpeechifySyncer(ProviderSyncer):
    provider_id = "speechify"
    source = "mixed"

    async def sync(self) -> SyncResult:
        voices_data, (tts_models, tts_notes) = await asyncio.gather(
            self._fetch_voices(),
            parse_models_from_docs(
                seed_urls=_DOCS_URLS,
                provider_id=self.provider_id,
                model_type="tts",
                guidance=_TTS_MODEL_GUIDANCE,
            ),
        )
        tts_voices = self._parse_voices(voices_data, tts_models)

        from_cache = isinstance(tts_notes, dict) and tts_notes.get("source") == "cache"
        sync_notes = (
            f"{len(tts_voices)} voices. {len(tts_models)} TTS models (cache)."
            if from_cache else
            f"{len(tts_voices)} voices. {len(tts_models)} TTS models."
        )

        return SyncResult(
            stt_models=[],
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            api_urls=[_VOICES_URL],
            docs_urls=_DOCS_URLS,
            notes=sync_notes,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_voices(self) -> list[dict]:
        if not settings.speechify_api_key:
            raise ValueError("SPEECHIFY_API_KEY is not set in .env")

        headers = {"Authorization": f"Bearer {settings.speechify_api_key}"}
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(_VOICES_URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            voices = data if isinstance(data, list) else (data.get("voices") or data.get("data") or [])
            return [v for v in voices if v.get("type") == "shared"]

    def _parse_voices(self, voices_data: list[dict], tts_models: list) -> list[SyncVoice]:
        all_model_ids = [m.model_id for m in tts_models]
        voices: list[SyncVoice] = []

        for v in voices_data:
            voice_id = v.get("id")
            if not voice_id:
                continue

            gender = _GENDER_MAP.get((v.get("gender") or "").lower())

            # Each entry: {"name": "simba-3.5", "languages": [{"locale": "te-IN", ...}]}.
            # (Older API versions used "model" instead of "name".)
            voice_models = v.get("models") or []
            model_names = [(m.get("name") or m.get("model")) for m in voice_models]
            compatible = sorted({n for n in model_names if n in all_model_ids})
            locales = [v.get("locale")] + [
                lang.get("locale") for m in voice_models for lang in (m.get("languages") or [])
                if isinstance(lang, dict)
            ]
            languages = list(dict.fromkeys(normalize_languages([loc for loc in locales if loc])))

            voices.append(SyncVoice(
                voice_id=voice_id,
                display_name=v.get("display_name") or voice_id,
                gender=gender,
                category="premade",
                languages=languages,
                preview_url=v.get("preview_audio") or None,
                tags=list(v.get("tags") or []),
                compatible_models=compatible,
                meta={k: val for k, val in {
                    "avatar_image": v.get("avatar_image"),
                    "staff_pick_rank": v.get("staff_pick_rank"),
                    "unlisted_models": sorted({n for n in model_names if n and n not in all_model_ids}) or None,
                }.items() if val},
            ))
        return voices


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = SpeechifySyncer()
    try:
        result = await syncer.sync()
    except httpx.HTTPStatusError as e:
        print(f"\nSpeechify API error ({e.response.status_code}): {e.response.text[:300]}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        print(
            f"  {m.model_id!r:25} {m.display_name!r:22} "
            f"langs={m.languages} is_default={m.is_default}"
        )

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) ===")
    for v in result.tts_voices[:20]:
        print(
            f"  {v.voice_id!r:20} {v.display_name!r:20} "
            f"gender={v.gender or '?':8} langs={v.languages}"
        )
    if len(result.tts_voices) > 20:
        print(f"  ... and {len(result.tts_voices) - 20} more")

    print(f"\nSource : {result.source}")
    print(f"Notes  : {result.notes}")
    print(f"Fetched: {result.fetched_at}")


if __name__ == "__main__":
    asyncio.run(_main())
