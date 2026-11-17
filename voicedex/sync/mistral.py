"""
Mistral AI Voxtral sync script.

Source: mixed
  - TTS voices: GET https://api.mistral.ai/v1/audio/voices (paginated, auth required)
  - TTS models: AI-parsed from docs
  - STT models: AI-parsed from docs

Voxtral is Mistral's audio stack — TTS (voxtral-mini-tts-2603) + STT (voxtral-mini-latest,
voxtral-mini-transcribe-realtime-2602). Launched March 2026.

Voice object shape (preset voices, 20 total):
  {
    "id": "casual_male",        -- or voice_id depending on API version
    "name": "Casual Male",
    "gender": "male",
    "languages": ["en"],
    "sample_url": "https://..."
  }

Pagination: limit + offset query params on GET /v1/audio/voices.
Auth: Authorization: Bearer API_KEY
Config: MISTRAL_API_KEY
"""

from __future__ import annotations

import asyncio

import httpx

from voicedex.config import settings
from voicedex.sync.ai_parser import parse_models_from_docs
from voicedex.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncResult, SyncVoice
from voicedex.sync.language import normalize_languages

_BASE_URL = "https://api.mistral.ai/v1"
_VOICES_URL = f"{_BASE_URL}/audio/voices"

_DOCS_URLS = [
    "https://docs.mistral.ai/models.md",
    "https://docs.mistral.ai/studio/audio/migrate-from-voxtral-2.md",
    "https://docs.mistral.ai/studio/audio/specs-and-limits/languages.md",
    "https://docs.mistral.ai/studio/audio/specs-and-limits/audio-formats.md",
    "https://docs.mistral.ai/studio/audio/specs-and-limits/limits.md",
]

_COMMON_GUIDANCE = (
    "Use canonical dated model ids (not '-latest' aliases; record aliases in meta). Keep deprecated "
    "models with a published retirement date (eol_date + meta.replacement); exclude retired ones. "
    "Public Preview models are beta. is_default=true for the model the docs say to start with."
)
_TTS_MODEL_GUIDANCE = "Return every Voxtral text-to-speech model. " + _COMMON_GUIDANCE
_STT_MODEL_GUIDANCE = (
    "Return every Voxtral transcription model (batch and realtime; streaming=true only for realtime). "
    + _COMMON_GUIDANCE
)

_GENDER_MAP = {"male": "male", "female": "female"}


def _age_label(age: int) -> str | None:
    if age < 18:
        return "child"
    if age < 30:
        return "young_adult"
    if age < 50:
        return "adult"
    return "mature"


class MistralSyncer(ProviderSyncer):
    provider_id = "mistral"
    source = "mixed"

    async def sync(self) -> SyncResult:
        voices_data, (tts_models, tts_notes), (stt_models, stt_notes) = await asyncio.gather(
            self._fetch_voices(),
            parse_models_from_docs(
                seed_urls=_DOCS_URLS,
                provider_id=self.provider_id,
                model_type="tts",
                guidance=_TTS_MODEL_GUIDANCE,
            ),
            parse_models_from_docs(
                seed_urls=_DOCS_URLS,
                provider_id=self.provider_id,
                model_type="stt",
                guidance=_STT_MODEL_GUIDANCE,
            ),
        )
        tts_voices = self._parse_voices(voices_data)

        from_cache = (
            isinstance(tts_notes, dict) and tts_notes.get("source") == "cache"
            and isinstance(stt_notes, dict) and stt_notes.get("source") == "cache"
        )
        sync_notes = (
            f"{len(tts_voices)} voices. {len(tts_models)} TTS models, "
            f"{len(stt_models)} STT models (cache)."
            if from_cache else
            f"{len(tts_voices)} voices. {len(tts_models)} TTS models, "
            f"{len(stt_models)} STT models."
        )

        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            api_urls=[_VOICES_URL],
            docs_urls=_DOCS_URLS,
            notes=sync_notes,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_voices(self) -> list[dict]:
        # The voices listing needs a (paid-plan) key; models come from public docs. Without a key we
        # publish models only — and once voices exist, the merge guard refuses an empty voice list,
        # so a missing key can never wipe them.
        if not settings.mistral_api_key:
            return []

        headers = {"Authorization": f"Bearer {settings.mistral_api_key}"}
        all_voices: list[dict] = []
        limit = 100

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            page = 1
            while True:
                resp = await client.get(
                    _VOICES_URL,
                    headers=headers,
                    params={"page": page, "page_size": limit},
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items") or []
                if not items:
                    break
                all_voices.extend(items)
                if page >= data.get("total_pages", 1):
                    break
                page += 1

        # Deduplicate by slug — API pagination may return overlapping pages
        seen: set[str] = set()
        unique: list[dict] = []
        for v in all_voices:
            key = v.get("slug") or v.get("id")
            if key and key not in seen:
                seen.add(key)
                unique.append(v)
        return unique

    def _parse_voices(self, voices_data: list[dict]) -> list[SyncVoice]:
        voices: list[SyncVoice] = []
        for v in voices_data:
            # slug is the API-usable voice identifier (e.g., "en_paul_neutral")
            voice_id = v.get("slug") or v.get("id")
            if not voice_id:
                continue

            gender = _GENDER_MAP.get((v.get("gender") or "").lower())

            # API returns languages as ["en_us"] — normalize underscore → hyphen
            raw_langs = [lang.replace("_", "-") for lang in (v.get("languages") or [])]
            languages = normalize_languages(raw_langs) if raw_langs else ["en"]

            age_raw = v.get("age")
            age = _age_label(age_raw) if age_raw else None

            tags = [t.lower() for t in (v.get("tags") or [])]

            voices.append(SyncVoice(
                voice_id=voice_id,
                display_name=v.get("name") or voice_id.replace("_", " ").title(),
                gender=gender,
                category="premade",
                languages=languages,
                age=age,
                use_cases=tags,
                compatible_models=["voxtral-mini-tts-2603"],
                meta={"color": v.get("color")},
            ))
        return voices


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = MistralSyncer()
    try:
        result = await syncer.sync()
    except httpx.HTTPStatusError as e:
        print(f"\nMistral API error ({e.response.status_code}): {e.response.text[:300]}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        print(f"  {m.model_id!r:45} {m.display_name!r:30} streaming={m.streaming}")

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        print(f"  {m.model_id!r:25} {m.display_name!r:25} langs={m.languages}")

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) ===")
    for v in result.tts_voices:
        print(
            f"  {v.voice_id!r:30} {v.display_name!r:22} "
            f"gender={v.gender or '?':6} langs={v.languages}"
        )

    print(f"\nSource : {result.source}")
    print(f"Notes  : {result.notes}")
    print(f"Fetched: {result.fetched_at}")


if __name__ == "__main__":
    asyncio.run(_main())
