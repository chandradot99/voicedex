"""
CAMB.ai sync script.

Source: mixed
  - TTS voices: GET https://client.camb.ai/apis/list-voices (no pagination, auth required)
  - TTS models: AI-parsed from docs (MARS8 model family)
  - STT models: AI-parsed from docs (transcription API)

Voice object shape:
  {
    "id": 147320,
    "voice_name": "Alice",
    "gender": 1,           -- 1=male, 2=female, 9=other/neutral
    "age": null,
    "language": 1,         -- internal integer language code (1–150)
    "description": null,
    "is_published": true
  }

Voice language is an internal integer — CAMB.ai supports cross-lingual synthesis
so all voices are set to ["*"] (all languages supported).

Auth: x-api-key header
Config: CAMBAI_API_KEY
"""

from __future__ import annotations

import asyncio

import httpx

from naaviq.config import settings
from naaviq.sync.ai_parser import parse_models_from_docs
from naaviq.sync.base import ProviderSyncer, SyncResult, SyncVoice, get_with_retry
from naaviq.sync.language import accent_from_languages, normalize_languages

_BASE_URL = "https://client.camb.ai"
_VOICES_URL = f"{_BASE_URL}/apis/list-voices"
_LANGUAGES_URL = f"{_BASE_URL}/apis/source-languages"   # integer id → locale ("en-us")

_DOCS_URLS = [
    "https://docs.camb.ai/models",
    "https://docs.camb.ai/language-support",
    "https://docs.camb.ai/api-reference/endpoint/create-tts-stream",
    "https://docs.camb.ai/api-reference/websockets/listen",
]

_TTS_MODEL_GUIDANCE = (
    "Return every MARS TTS model id the API accepts (exclude on-device-only models with no API id). "
    "Beta-labelled models are beta. is_default=true for the model the docs recommend starting with."
)
_STT_MODEL_GUIDANCE = (
    "Return every speech-to-text model id the API accepts. Endpoints that take no model parameter are "
    "not models. is_default=true for the recommended model."
)

# list-voices returns CAMB's stock library *and* the caller's own (possibly cloned) voices, with no
# field telling them apart and no account-identity endpoint. Publish only voices owned by CAMB's
# library accounts — safe by default: a new library owner is skipped (and reported) until reviewed
# and added here; a user's private clone can never leak.
_LIBRARY_OWNER_IDS = {50358, 74991, 191766}

_GENDER_MAP = {1: "male", 2: "female", 9: "neutral"}


class CambAISyncer(ProviderSyncer):
    provider_id = "cambai"
    source = "mixed"

    async def sync(self) -> SyncResult:
        (voices_data, lang_map), (tts_models, tts_notes), (stt_models, stt_notes) = await asyncio.gather(
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
        tts_voices, skipped = self._parse_voices(voices_data, lang_map)
        sync_notes = f"{len(tts_voices)} library voices. {len(tts_models)} TTS, {len(stt_models)} STT models."
        if skipped:
            # Surfaces in sync output: review, and add to _LIBRARY_OWNER_IDS only if it's a CAMB library.
            sync_notes += " SKIPPED non-library voices by owner: " + ", ".join(
                f"{owner}={n}" for owner, n in sorted(skipped.items()))

        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            api_urls=[_VOICES_URL, _LANGUAGES_URL],
            docs_urls=_DOCS_URLS,
            notes=sync_notes,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_voices(self) -> tuple[list[dict], dict[int, str]]:
        """(voices, {language id → BCP-47 locale})."""
        if not settings.cambai_api_key:
            raise ValueError("CAMBAI_API_KEY is not set in .env")

        headers = {"x-api-key": settings.cambai_api_key}
        async with httpx.AsyncClient(timeout=60) as client:
            vresp, lresp = await asyncio.gather(
                get_with_retry(client, _VOICES_URL, headers=headers),
                get_with_retry(client, _LANGUAGES_URL, headers=headers),
            )
            vresp.raise_for_status()
            lresp.raise_for_status()
        data = vresp.json()
        voices = data if isinstance(data, list) else (data.get("voices") or data.get("data") or [])
        lang_map = {
            int(x["id"]): normalize_languages([x["short_name"]])[0]
            for x in lresp.json() if x.get("id") is not None and x.get("short_name")
        }
        return voices, lang_map

    def _parse_voices(self, voices_data: list[dict], lang_map: dict[int, str]) -> tuple[list[SyncVoice], dict]:
        voices: list[SyncVoice] = []
        skipped: dict = {}
        for v in voices_data:
            voice_id = v.get("id")
            if voice_id is None:
                continue
            if v.get("owner_id") not in _LIBRARY_OWNER_IDS:
                skipped[v.get("owner_id")] = skipped.get(v.get("owner_id"), 0) + 1
                continue

            native = lang_map.get(v.get("language"))
            voices.append(SyncVoice(
                voice_id=str(voice_id),
                display_name=v.get("voice_name") or str(voice_id),
                gender=_GENDER_MAP.get(v.get("gender")),
                category="premade",
                # Native locale. MARS voices can also speak other languages (cross-lingual) —
                # recorded in meta rather than claiming every language for every voice.
                languages=[native] if native else [],
                accent=accent_from_languages([native]) if native else None,
                age=_age_label(v["age"]) if v.get("age") else None,
                description=v.get("description") or None,
                use_cases=list(v.get("tags") or []),
                compatible_models=["*"],  # all library voices work with all MARS models
                meta={"cross_lingual": True},
            ))
        return voices, skipped


# ── Helpers ───────────────────────────────────────────────────────────────────

def _age_label(age: int) -> str | None:
    if age < 18:
        return "child"
    if age < 30:
        return "young_adult"
    if age < 50:
        return "adult"
    return "mature"


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = CambAISyncer()
    try:
        result = await syncer.sync()
    except httpx.HTTPStatusError as e:
        print(f"\nCAMB.ai API error ({e.response.status_code}): {e.response.text[:300]}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        print(f"  {m.model_id!r:20} {m.display_name!r:25} langs={m.languages}")

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        print(
            f"  {m.model_id!r:22} {m.display_name!r:22} "
            f"langs={m.languages} is_default={m.is_default}"
        )

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) ===")
    for v in result.tts_voices[:20]:
        print(
            f"  {v.voice_id!r:8} {v.display_name!r:20} "
            f"gender={v.gender or '?':7} age={v.age or '?'}"
        )
    if len(result.tts_voices) > 20:
        print(f"  ... and {len(result.tts_voices) - 20} more")

    print(f"\nSource : {result.source}")
    print(f"Notes  : {result.notes}")
    print(f"Fetched: {result.fetched_at}")


if __name__ == "__main__":
    asyncio.run(_main())
