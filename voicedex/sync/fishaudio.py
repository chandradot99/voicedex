"""
Fish Audio sync script.

Source: mixed
  - TTS voices: GET https://api.fish.audio/model (paginated, auth required)
  - TTS models: AI-parsed from docs (no /models endpoint)
  - STT models: AI-parsed from docs (beta ASR endpoint)

Voice object shape (abbreviated):
  {
    "_id": "...",
    "type": "tts",
    "title": "Voice Name",
    "description": "...",
    "cover_image": "...",
    "tags": ["tag1", "tag2"],
    "languages": ["en", "zh"],
    "visibility": "public",
    "state": "trained",
    "like_count": 42,
    "task_count": 1000,
    "train_mode": "fast" | "full",
    "author": {"_id": "...", "nickname": "username", "avatar": "..."}
  }

Pagination: page_size + page_number query params.
Only Fish Audio's own "Fish Official" voices are published (author filter, all pages). The public
library is mostly user-uploaded community clones — including unlicensed impersonations of real people
and characters — and a popularity-capped slice of it churns on every sync, so it is deliberately
excluded. Usage counters (like/task counts) are not stored: they change daily and carry no catalog
meaning.

Auth: Authorization: Bearer API_KEY
Config: FISH_AUDIO_API_KEY
"""

from __future__ import annotations

import asyncio

import httpx

from voicedex.config import settings
from voicedex.sync.ai_parser import parse_models_from_docs
from voicedex.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.language import normalize_languages

_BASE_URL = "https://api.fish.audio"
_MODELS_URL = f"{_BASE_URL}/model"

_DOCS_URLS = [
    "https://docs.fish.audio/llms.txt",
    "https://docs.fish.audio/developer-guide/models-pricing/models-overview",
    "https://docs.fish.audio/developer-guide/models-pricing/deprecations",
    "https://docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits",
    "https://docs.fish.audio/features/speech-to-text",
]

_TTS_MODEL_GUIDANCE = (
    "Return every TTS model id the API accepts (the `model` header/param). Keep deprecated models "
    "with a published shutdown date (eol_date); exclude retired ones. is_default=true for the model "
    "the docs recommend for production."
)
_STT_MODEL_GUIDANCE = (
    "Return every speech-to-text model id the API accepts (batch and realtime). Preview models are "
    "beta. is_default=true for the recommended model."
)

_OFFICIAL_AUTHOR_ID = "d8b0991f96b44e489422ca2ddf0bd31d"   # "Fish Official"
_OFFICIAL_AUTHOR_NAME = "Fish Official"
_VOICE_PAGE_SIZE = 100
_MAX_PAGES = 50


class FishAudioSyncer(ProviderSyncer):
    provider_id = "fishaudio"
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
            api_urls=[_MODELS_URL],
            docs_urls=_DOCS_URLS,
            notes=sync_notes,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_voices(self) -> list[dict]:
        if not settings.fish_audio_api_key:
            raise ValueError("FISH_AUDIO_API_KEY is not set in .env")

        headers = {"Authorization": f"Bearer {settings.fish_audio_api_key}"}
        voices: list[dict] = []
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for page in range(1, _MAX_PAGES + 1):
                resp = await get_with_retry(client, _MODELS_URL, headers=headers, params={
                    "type": "tts", "author_id": _OFFICIAL_AUTHOR_ID,
                    "page_size": _VOICE_PAGE_SIZE, "page_number": page,
                })
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items") or []
                voices.extend(items)
                if not items or len(voices) >= data.get("total", 0):
                    return voices
        raise RuntimeError(f"Fish Audio voice pagination exceeded {_MAX_PAGES} pages")

    def _parse_voices(self, voices_data: list[dict]) -> list[SyncVoice]:
        voices: list[SyncVoice] = []
        for v in voices_data:
            voice_id = v.get("_id")
            if not voice_id or v.get("state") != "trained" or v.get("dmca_taken_down"):
                continue
            # Defense in depth: never publish a community voice even if the filter misbehaves.
            if (v.get("author") or {}).get("nickname") != _OFFICIAL_AUTHOR_NAME:
                continue

            tags = [t.lower() for t in (v.get("tags") or [])]
            gender = "female" if "female" in tags else "male" if "male" in tags else None
            preview_url = None
            samples = v.get("samples") or []
            if samples and isinstance(samples[0], dict):
                preview_url = samples[0].get("url") or samples[0].get("audio")

            voices.append(SyncVoice(
                voice_id=voice_id,
                display_name=v.get("title") or voice_id,
                gender=gender,
                category="premade",
                languages=normalize_languages(v.get("languages") or []),
                description=v.get("description") or None,
                preview_url=preview_url,
                tags=[t for t in tags if _is_public_tag(t)],
                compatible_models=["*"],  # all voices work with all Fish Audio TTS models
                meta={k: val for k, val in {
                    "train_mode": v.get("train_mode"),
                    "cover_image": v.get("cover_image"),
                }.items() if val},
            ))
        return voices


_INTERNAL_TAGS = {"voice-factory"}


def _is_public_tag(tag: str) -> bool:
    """Drop gender (own field), locale codes ("te-in"), and Fish's internal batch labels
    ("cale_oct_26", "prompt_test_oct_26", "voice-factory")."""
    import re
    return not (tag in {"male", "female"} or tag in _INTERNAL_TAGS or "_" in tag or any(c.isdigit() for c in tag)
                or re.fullmatch(r"[a-z]{2,3}-[a-z]{2}", tag))


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = FishAudioSyncer()
    try:
        result = await syncer.sync()
    except httpx.HTTPStatusError as e:
        print(f"\nFish Audio API error ({e.response.status_code}): {e.response.text[:300]}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        print(f"  {m.model_id!r:25} {m.display_name!r:30} langs={m.languages}")

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        print(
            f"  {m.model_id!r:12} {m.display_name!r:28} "
            f"langs={m.languages} is_default={m.is_default}"
        )

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) ===")
    for v in result.tts_voices[:20]:
        print(
            f"  {v.voice_id!r:36} {v.display_name!r:25} "
            f"lang={v.languages} gender={v.gender}"
        )
    if len(result.tts_voices) > 20:
        print(f"  ... and {len(result.tts_voices) - 20} more")

    print(f"\nSource : {result.source}")
    print(f"Notes  : {result.notes}")
    print(f"Fetched: {result.fetched_at}")


if __name__ == "__main__":
    asyncio.run(_main())
