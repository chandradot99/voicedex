"""
Smallest AI sync script.

Source: mixed
  - TTS voices: GET https://api.smallest.ai/waves/v1/{model}/get_voices (auth required)
  - TTS models: AI-parsed from docs
  - STT models: AI-parsed from docs
  - STS models (Hydra): AI-parsed from docs

Voice endpoint is per-model. Voices are fetched for the default model (lightning-v3.1).

Voice object shape:
  {
    "voiceId": "magnus",
    "displayName": "Magnus",
    "tags": {
      "language": ["en"],
      "accent": "american",
      "gender": "male"
    }
  }

Auth: Authorization: Bearer API_KEY
Config: SMALLEST_API_KEY
"""

from __future__ import annotations

import asyncio

import httpx

from voicedex.config import settings
from voicedex.sync.ai_parser import parse_models_from_docs
from voicedex.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.language import language_from_name

_BASE_URL = "https://api.smallest.ai/waves/v1"
# Voices are listed per model: /{model-slug}/get_voices, slug = model id with "_" → "-".
_VOICES_URL = _BASE_URL + "/{slug}/get_voices"

_DOCS_URLS = [
    "https://docs.smallest.ai/model-cards/compare",
    "https://docs.smallest.ai/api-reference/deprecations/models",
]

_STS_DOCS_URLS = [
    "https://docs.smallest.ai/model-cards/speech-to-speech/hydra",
    "https://docs.smallest.ai/api-reference/deprecations/models",
]

_TTS_MODEL_GUIDANCE = (
    "Return every Lightning TTS model id the API accepts (exact ids). Keep deprecated models with a "
    "published shutdown date (eol_date); exclude those deprecated with no date. is_default=true for "
    "the model the docs call current."
)
_STT_MODEL_GUIDANCE = (
    "Return every Pulse STT model id the API accepts. is_default=true for the model the docs call current."
)

_STS_MODEL_GUIDANCE = (
    "Return every Hydra speech-to-speech model id accepted in ?model= on the s2s WebSocket (exact ids, not "
    "deprecated bare tags). is_default=true for the version the changelog/deprecations call current."
)

_GENDER_MAP = {"male": "male", "female": "female", "neutral": "neutral"}


class SmallestAISyncer(ProviderSyncer):
    provider_id = "smallestai"
    source = "mixed"

    async def sync(self) -> SyncResult:
        (tts_models, tts_notes), (stt_models, stt_notes), (sts_models, _) = await asyncio.gather(
            parse_models_from_docs(seed_urls=_DOCS_URLS, provider_id=self.provider_id,
                                   model_type="tts", guidance=_TTS_MODEL_GUIDANCE),
            parse_models_from_docs(seed_urls=_DOCS_URLS, provider_id=self.provider_id,
                                   model_type="stt", guidance=_STT_MODEL_GUIDANCE),
            parse_models_from_docs(seed_urls=_STS_DOCS_URLS, provider_id=self.provider_id,
                                   model_type="sts", guidance=_STS_MODEL_GUIDANCE),
        )
        # Voices are per-model endpoints, so the model list decides which endpoints to query.
        voices_data = await self._fetch_voices_by_model([_slug(m.model_id) for m in tts_models])
        tts_voices = self._parse_voices(voices_data, [m.model_id for m in tts_models])

        from_cache = (
            isinstance(tts_notes, dict) and tts_notes.get("source") == "cache"
            and isinstance(stt_notes, dict) and stt_notes.get("source") == "cache"
        )
        sync_notes = (
            f"{len(tts_voices)} voices. {len(tts_models)} TTS models, "
            f"{len(stt_models)} STT, {len(sts_models)} STS models (cache)."
            if from_cache else
            f"{len(tts_voices)} voices. {len(tts_models)} TTS models, "
            f"{len(stt_models)} STT, {len(sts_models)} STS models."
        )

        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            sts_models=sts_models,
            tts_voices=tts_voices,
            source=self.source,
            api_urls=[_VOICES_URL.format(slug="{model}")],
            docs_urls=list(dict.fromkeys(_DOCS_URLS + _STS_DOCS_URLS)),
            notes=sync_notes,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_voices_by_model(self, slugs: list[str]) -> dict[str, list[dict]]:
        """{endpoint slug: voices} for each TTS model; models without a voices endpoint are skipped."""
        if not settings.smallest_api_key:
            raise ValueError("SMALLEST_API_KEY is not set in .env")
        headers = {"Authorization": f"Bearer {settings.smallest_api_key}"}
        out: dict[str, list[dict]] = {}
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for slug in slugs:
                resp = await get_with_retry(client, _VOICES_URL.format(slug=slug), headers=headers)
                if resp.status_code == 404:
                    continue  # model without its own voices endpoint (e.g. dated snapshots)
                resp.raise_for_status()
                out[slug] = resp.json().get("voices") or []
        if not out:
            raise RuntimeError("Smallest AI returned no voices from any model endpoint")
        return out

    def _parse_voices(self, by_slug: dict[str, list[dict]], model_ids: list[str]) -> list[SyncVoice]:
        slug_to_model = {_slug(m): m for m in model_ids}
        entries: dict[str, list[tuple[str, dict]]] = {}
        for slug, items in by_slug.items():
            model = slug_to_model.get(slug)
            if model is None:
                continue
            for v in items:
                if v.get("voiceId"):
                    entries.setdefault(v["voiceId"], []).append((model, v))

        voices: list[SyncVoice] = []
        for voice_id, pairs in entries.items():
            v = pairs[0][1]  # metadata from the first (= preferred, docs order) model
            tags = v.get("tags") or {}
            names = list(tags.get("recommendedLanguages") or []) + list(tags.get("language") or [])
            languages = list(dict.fromkeys(c for c in (language_from_name(n) for n in names) if c))
            voices.append(SyncVoice(
                voice_id=voice_id,
                display_name=v.get("displayName") or voice_id,
                gender=_GENDER_MAP.get((tags.get("gender") or "").lower()),
                category="premade",
                languages=languages,
                accent=(tags.get("accent") or None),
                age=(tags.get("age") or None),
                use_cases=list(tags.get("usecases") or []),
                compatible_models=sorted({m for m, _ in pairs}),
                meta={k: val for k, val in {"emotions": tags.get("emotions") or None}.items() if val},
            ))
        return voices


def _slug(model_id: str) -> str:
    return model_id.replace("_", "-")


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = SmallestAISyncer()
    try:
        result = await syncer.sync()
    except httpx.HTTPStatusError as e:
        print(f"\nSmallest AI error ({e.response.status_code}): {e.response.text[:300]}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        print(f"  {m.model_id!r:12} {m.display_name!r:20} langs={m.languages}")

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        print(
            f"  {m.model_id!r:18} {m.display_name!r:20} "
            f"langs={m.languages} is_default={m.is_default}"
        )

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) ===")
    for v in result.tts_voices:
        print(
            f"  {v.voice_id!r:20} {v.display_name!r:22} "
            f"gender={v.gender or '?':6} accent={v.accent or '?':12} langs={v.languages}"
        )

    print(f"\nSource : {result.source}")
    print(f"Notes  : {result.notes}")
    print(f"Fetched: {result.fetched_at}")


if __name__ == "__main__":
    asyncio.run(_main())
