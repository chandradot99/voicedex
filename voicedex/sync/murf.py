"""
Murf AI sync script.

Source: mixed
  - TTS voices: GET https://api.murf.ai/v1/speech/voices (API)
  - TTS models: AI-parsed from docs (no /models endpoint); languages derived from live voice API
  - STT: not offered — stt_models=[]

Voice API response fields:
  voiceId           → voice_id
  displayName       → display_name
  gender            → gender ("Male" → "male", "NonBinary" → "neutral")
  locale            → primary language
  supportedLocales  → additional languages + styles per locale
  description       → meta

Auth: api-key header, MURF_API_KEY env var.
"""

from __future__ import annotations

import asyncio
import re

import httpx

from voicedex.config import settings
from voicedex.sync.ai_parser import parse_models_from_docs
from voicedex.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncResult, SyncVoice
from voicedex.sync.language import ACCENT_MAP, normalize_languages

_VOICES_URL = "https://api.murf.ai/v1/speech/voices"

_DOCS_URLS = [
    "https://murf.ai/api/docs/llms.txt",
    "https://murf.ai/api/docs/text-to-speech-models/falcon-2-1.md",
    "https://murf.ai/api/docs/text-to-speech-models/gen-2.md",
]

_MODEL_GUIDANCE = (
    "Return every TTS model id the API accepts (exact strings, case-sensitive). is_default=true for "
    "the model the docs recommend; note in meta which endpoints (streaming / non-streaming) accept "
    "each model. Languages per model from its model page. Per-character pricing when published."
)

# Murf-specific locale codes that aren't BCP-47.
_MURF_LOCALES = {"en-UK": "en-GB", "en-SCOTT": "en-GB"}
_MURF_ACCENTS = {"en-UK": "british", "en-SCOTT": "scottish"}

_GENDER_MAP: dict[str, str] = {
    "male":      "male",
    "female":    "female",
    "nonbinary": "neutral",
}


class MurfAISyncer(ProviderSyncer):
    provider_id = "murf"
    source = "mixed"

    async def sync(self) -> SyncResult:
        voices_data, (tts_models, notes) = await asyncio.gather(
            self._fetch_voices(),
            parse_models_from_docs(
                seed_urls=_DOCS_URLS,
                provider_id=self.provider_id,
                model_type="tts",
                guidance=_MODEL_GUIDANCE,
            ),
        )
        tts_voices = self._parse_voices(voices_data)
        all_langs = {lang for v in tts_voices for lang in v.languages}

        from_cache = isinstance(notes, dict) and notes.get("source") == "cache"
        sync_notes = (
            f"{len(tts_voices)} voices. {len(tts_models)} TTS models (cache). "
            f"{len(all_langs)} langs from API."
            if from_cache else
            f"{len(tts_voices)} voices. {len(tts_models)} TTS models. "
            f"{len(all_langs)} langs from API."
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
        if not settings.murf_api_key:
            raise ValueError("MURF_API_KEY is not set in .env")

        headers = {"api-key": settings.murf_api_key}

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(_VOICES_URL, headers=headers)
            resp.raise_for_status()
            body = resp.json()

        if isinstance(body, list):
            return body
        return body.get("voices", body.get("items", []))

    def _parse_voices(self, voices_data: list[dict]) -> list[SyncVoice]:
        voices: list[SyncVoice] = []
        for v in voices_data:
            voice_id = v.get("voiceId")
            if not voice_id:
                continue
            locale = v.get("locale") or ""
            supported = v.get("supportedLocales") or {}
            raw_locales = [loc for loc in [locale, *supported.keys()] if loc]
            languages = list(dict.fromkeys(normalize_languages([_MURF_LOCALES.get(x, x) for x in raw_locales])))
            styles = sorted({st for loc in supported.values() for st in (loc.get("availableStyles") or [])}
                            | set(v.get("availableStyles") or []))

            voices.append(SyncVoice(
                voice_id=voice_id,
                display_name=re.sub(r"\s*\((?:M|F|NB)\)\s*$", "", v.get("displayName") or "") or voice_id,
                gender=_parse_gender(v.get("gender")),
                category="premade",
                languages=languages,
                accent=_accent_from_locale(locale),
                age=(v.get("description") or "").replace("-", " ").lower() or None,  # Murf puts age here
                compatible_models=["*"],
                meta={k: val for k, val in {
                    "styles": styles or None,
                    "accent_label": v.get("accent"),
                    "locale_details": {_MURF_LOCALES.get(k, k): loc.get("detail") for k, loc in supported.items()} or None,
                }.items() if val},
            ))
        return voices


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_gender(value: str | None) -> str | None:
    if not value:
        return None
    return _GENDER_MAP.get(value.lower())


_MURF_REGION_TO_ACCENT: dict[str, str] = {
    "UK": "british",
    "Scott": "scottish",
}


def _accent_from_locale(locale: str) -> str | None:
    if locale in _MURF_ACCENTS:
        return _MURF_ACCENTS[locale]
    parts = locale.split("-")
    if len(parts) >= 2:
        region = parts[1]
        return _MURF_REGION_TO_ACCENT.get(region) or ACCENT_MAP.get(region.upper())
    return None


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = MurfAISyncer()
    try:
        result = await syncer.sync()
    except ValueError as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise SystemExit(1)
    except httpx.HTTPStatusError as e:
        print(f"\nMurf API error ({e.response.status_code}): {e.response.text[:300]}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        print(
            f"  {m.model_id!r:15} {m.display_name!r:20} "
            f"langs={len(m.languages)} is_default={m.is_default}"
        )

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) — showing first 20 ===")
    for v in result.tts_voices[:20]:
        print(
            f"  {v.voice_id!r:25} {v.display_name!r:20} "
            f"gender={v.gender or '?':6} accent={v.accent or '?':12} "
            f"langs={v.languages}"
        )
    if len(result.tts_voices) > 20:
        print(f"  ... and {len(result.tts_voices) - 20} more")

    print(f"\nSource: {result.source}")
    print(f"Fetched at: {result.fetched_at}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_main())
