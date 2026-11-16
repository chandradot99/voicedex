"""
Typecast AI sync script.

Source: mixed
  - TTS voices: GET https://api.typecast.ai/v2/voices (no pagination, auth required)
  - TTS models: AI-parsed from docs (SSFM model family)
  - STT: not offered — stt_models=[]

Voice object shape:
  {
    "voice_id": "tc_abc123",
    "voice_name": "Emily",
    "gender": "female",       -- "male" | "female"
    "age": "young_adult",     -- "child" | "teen" | "young_adult" | "adult" | "mature"
    "models": ["ssfm-v30", "ssfm-v21"],
    "use_cases": ["narration", "social_media"],
    "language": "eng"         -- ISO 639-3 code
  }

Auth: X-API-KEY header
Config: TYPECAST_API_KEY
"""

from __future__ import annotations

import asyncio

import httpx

from naaviq.config import settings
from naaviq.sync.ai_parser import parse_models_from_docs
from naaviq.sync.base import ProviderSyncer, SyncResult, SyncVoice

_BASE_URL = "https://api.typecast.ai"
_VOICES_URL = f"{_BASE_URL}/v2/voices"

_DOCS_URLS = [
    "https://typecast.ai/docs/llms.txt",
    "https://typecast.ai/docs/api-reference/text-to-speech/text-to-speech",
    "https://typecast.ai/docs/changelog",
    "https://typecast.ai/pricing/api/",
]

_TTS_MODEL_GUIDANCE = (
    "Return every SSFM model id the API accepts. is_default=true for the model the docs recommend. "
    "Languages per model as BCP-47; emotion capability where emotion presets are documented."
)

# Stock voices are "original"; anything else (e.g. a user's custom/cloned voice) is never published.
_PUBLIC_VOICE_TYPES = {"original"}

_GENDER_MAP = {"male": "male", "female": "female"}


class TypecastAISyncer(ProviderSyncer):
    provider_id = "typecastai"
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
        if not settings.typecast_api_key:
            raise ValueError("TYPECAST_API_KEY is not set in .env")

        headers = {"X-API-KEY": settings.typecast_api_key}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(_VOICES_URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else (data.get("voices") or data.get("data") or [])

    def _parse_voices(self, voices_data: list[dict], tts_models: list) -> list[SyncVoice]:
        model_langs = {m.model_id: m.languages for m in tts_models}
        voices: list[SyncVoice] = []

        for v in voices_data:
            voice_id = v.get("voice_id")
            if not voice_id or v.get("voice_type", "original") not in _PUBLIC_VOICE_TYPES:
                continue

            raw_models = [m for m in (v.get("models") or []) if isinstance(m, dict) and m.get("version")]
            compatible = sorted(m["version"] for m in raw_models if m["version"] in model_langs)
            emotions = {m["version"]: m.get("emotions") or [] for m in raw_models if m["version"] in model_langs}
            # No per-voice language in the API; SSFM voices speak their models' languages.
            languages = sorted({lang for mid in compatible for lang in model_langs[mid]})

            voices.append(SyncVoice(
                voice_id=voice_id,
                display_name=v.get("voice_name") or voice_id,
                gender=_GENDER_MAP.get((v.get("gender") or "").lower()),
                category="premade",
                languages=languages,
                age=(v.get("age") or "").replace("_", " ") or None,
                use_cases=list(v.get("use_cases") or []),
                compatible_models=compatible,
                capabilities=["emotion"] if any(emotions.values()) else [],
                meta={"emotions": emotions} if any(emotions.values()) else {},
            ))
        return voices


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = TypecastAISyncer()
    try:
        result = await syncer.sync()
    except httpx.HTTPStatusError as e:
        print(f"\nTypecast AI API error ({e.response.status_code}): {e.response.text[:300]}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        print(
            f"  {m.model_id!r:15} {m.display_name!r:18} "
            f"langs={m.languages} is_default={m.is_default}"
        )

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) ===")
    for v in result.tts_voices[:20]:
        print(
            f"  {v.voice_id!r:20} {v.display_name!r:20} "
            f"gender={v.gender or '?':7} age={v.age or '?':12} langs={v.languages}"
        )
    if len(result.tts_voices) > 20:
        print(f"  ... and {len(result.tts_voices) - 20} more")

    print(f"\nSource : {result.source}")
    print(f"Notes  : {result.notes}")
    print(f"Fetched: {result.fetched_at}")


if __name__ == "__main__":
    asyncio.run(_main())
