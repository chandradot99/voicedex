"""
Inworld AI sync script.

Source: mixed
  - TTS voices: GET https://api.inworld.ai/voices/v1/voices (API)
  - TTS models: AI-parsed from docs (no /models endpoint)
  - STT models: AI-parsed from docs (no /models endpoint)

Voice API response shape:
  {
    "voices": [...],
    "nextPageToken": "...",
    "totalSize": 135
  }

Each voice:
  {
    "voiceId": "Loretta",
    "name": "Loretta",
    "displayName": "Loretta",
    "langCode": "EN_US",
    "gender": "female",
    "ageGroup": "middle_aged",
    "description": "Inviting, folksy Southern female voice...",
    "tags": ["inviting", "folksy", "southern", ...],
    "categories": ["interactive_media"],
    "source": "SYSTEM"
  }

Auth: Authorization: Basic <base64_key>, INWORLD_API_KEY env var.
"""

from __future__ import annotations

import asyncio

import httpx

from voicedex.config import settings
from voicedex.sync.ai_parser import parse_models_from_docs
from voicedex.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncResult, SyncVoice
from voicedex.sync.language import normalize_languages

_VOICES_URL = "https://api.inworld.ai/voices/v1/voices"

_TTS_DOCS_SEED_URLS = [
    "https://docs.inworld.ai/tts/tts-models.md",
    "https://inworld.ai/pricing",
    "https://docs.inworld.ai/llms.txt",
]
_TTS_MODEL_GUIDANCE = (
    "Return every TTS model id the API accepts. Exclude models already shut down; keep deprecated "
    "models that still work only if a shutdown date is published (eol_date). is_default=true for the "
    "model the docs recommend for production."
)

_STT_DOCS_SEED_URLS = [
    "https://docs.inworld.ai/stt/overview.md",
    "https://docs.inworld.ai/stt/third-party.md",
    "https://docs.inworld.ai/stt/languages.md",
]
_STT_MODEL_GUIDANCE = (
    "Return every STT model id the API accepts, including third-party models Inworld routes to "
    "(exact provider-prefixed ids; record the upstream provider in meta.upstream). is_default=true "
    "for the model Inworld's own endpoints run by default."
)

_STS_DOCS_SEED_URLS = [
    "https://docs.ultravox.ai/",
    "https://www.ultravox.ai/pricing",
]
_STS_MODEL_GUIDANCE = (
    "Inworld acquired Ultravox (2026). Return the speech-to-speech / realtime voice models callable "
    "through the Ultravox API by exact model id, with languages, interfaces and per-minute pricing as "
    "published. meta.product='Ultravox'. Exactly one is_default: the model Ultravox uses by default."
)

# Inworld accent labels → our accent format
_ACCENT_MAP: dict[str, str] = {
    "american":   "american",
    "british":    "british",
    "australian": "australian",
    "indian":     "indian",
    "canadian":   "canadian",
    "irish":      "irish",
}


class InworldAISyncer(ProviderSyncer):
    provider_id = "inworld"
    source = "mixed"

    async def sync(self) -> SyncResult:
        voices_data, (tts_models, tts_notes), (stt_models, stt_notes), (sts_models, _) = await asyncio.gather(
            self._fetch_voices(),
            parse_models_from_docs(
                seed_urls=_TTS_DOCS_SEED_URLS,
                provider_id=self.provider_id,
                model_type="tts",
                guidance=_TTS_MODEL_GUIDANCE,
            ),
            parse_models_from_docs(
                seed_urls=_STT_DOCS_SEED_URLS,
                provider_id=self.provider_id,
                model_type="stt",
                guidance=_STT_MODEL_GUIDANCE,
            ),
            parse_models_from_docs(
                seed_urls=_STS_DOCS_SEED_URLS,
                provider_id=self.provider_id,
                model_type="sts",
                guidance=_STS_MODEL_GUIDANCE,
            ),
        )

        notes_parts = []
        if tts_notes:
            notes_parts.append(f"TTS: {tts_notes}")
        if stt_notes:
            notes_parts.append(f"STT: {stt_notes}")

        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            tts_voices=self._parse_voices(voices_data),
            sts_models=sts_models,
            source=self.source,
            api_urls=[_VOICES_URL],
            docs_urls=_TTS_DOCS_SEED_URLS + _STT_DOCS_SEED_URLS + _STS_DOCS_SEED_URLS,
            notes="; ".join(notes_parts) if notes_parts else None,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_voices(self) -> list[dict]:
        if not settings.inworld_api_key:
            raise ValueError("INWORLD_API_KEY is not set in .env")

        headers = {"Authorization": f"Basic {settings.inworld_api_key}"}
        all_voices: list[dict] = []

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            page_token: str | None = None
            while True:
                params: dict[str, str] = {}
                if page_token:
                    params["pageToken"] = page_token

                resp = await client.get(_VOICES_URL, headers=headers, params=params)
                resp.raise_for_status()
                body = resp.json()

                all_voices.extend(body.get("voices", []))

                page_token = body.get("nextPageToken")
                if not page_token:
                    break

        return all_voices

    def _parse_voices(self, voices_data: list[dict]) -> list[SyncVoice]:
        voices: list[SyncVoice] = []
        for v in voices_data:
            if v.get("source") not in ("SYSTEM", None):
                continue  # user-cloned / workspace voices are private — never publish them

            voice_id = v.get("voiceId") or v.get("name")
            if not voice_id:
                continue

            # `languageCode` is already BCP-47 ("hi-IN"); `langCode` is the legacy "HI_IN" form.
            primary = v.get("languageCode") or _normalize_lang_code(v.get("langCode") or "")
            extra = [loc.get("languageCode") for loc in (v.get("localizations") or [])
                     if isinstance(loc, dict) and loc.get("languageCode")]
            languages = list(dict.fromkeys(normalize_languages([x for x in [primary, *extra] if x])))

            voices.append(SyncVoice(
                voice_id=voice_id,
                display_name=v.get("displayName") or v.get("name") or voice_id,
                gender=_parse_gender(v.get("gender")),
                category="premade",
                languages=languages,
                accent=_parse_accent_from_tags(v.get("tags") or []),
                age=_parse_age(v.get("ageGroup")),
                description=v.get("description"),
                use_cases=list(v.get("categories") or []),
                tags=list(v.get("tags") or []),
                compatible_models=["*"],
            ))
        return voices


# ── Field parsers ─────────────────────────────────────────────────────────────

def _parse_gender(value: str | None) -> str | None:
    if not value:
        return None
    g = value.lower()
    if g in ("male", "female", "neutral"):
        return g
    return None


def _parse_age(value: str | None) -> str | None:
    if not value:
        return None
    a = value.lower().replace("-", "_")
    if a in ("age_unspecified", "unspecified"):
        return None
    return a


def _parse_accent_from_tags(tags: list[str]) -> str | None:
    for tag in tags:
        mapped = _ACCENT_MAP.get(tag.lower())
        if mapped:
            return mapped
    return None


def _normalize_lang_code(code: str) -> str:
    """Convert Inworld lang codes like 'EN_US' to BCP-47 'en-US'."""
    return code.replace("_", "-")


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = InworldAISyncer()
    try:
        result = await syncer.sync()
    except ValueError as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise SystemExit(1)
    except httpx.HTTPStatusError as e:
        print(f"\nInworld API error ({e.response.status_code}): {e.response.text[:300]}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        print(
            f"  {m.model_id!r:25} {m.display_name!r:30} "
            f"langs={m.languages} is_default={m.is_default}"
        )

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        print(
            f"  {m.model_id!r:20} {m.display_name!r:20} "
            f"langs={len(m.languages)} is_default={m.is_default}"
        )

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) ===")
    for v in result.tts_voices:
        print(
            f"  {v.voice_id!r:20} {v.display_name!r:20} "
            f"gender={v.gender or '?':6} accent={v.accent or '?':12} "
            f"age={v.age or '?':10} langs={v.languages}"
        )

    print(f"\nSource: {result.source}")
    print(f"Fetched at: {result.fetched_at}")
    if result.notes:
        print(f"\nNotes: {result.notes}")


if __name__ == "__main__":
    asyncio.run(_main())
