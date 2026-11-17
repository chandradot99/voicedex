"""
ElevenLabs sync script.

Source: mixed
  - TTS models : GET /v1/models (entries with can_do_text_to_speech=true)
  - STT models : AI-parsed from https://elevenlabs.io/docs/capabilities/speech-to-text
                 (Scribe family — not returned by /v1/models)
  - TTS voices : GET /v2/voices (premade voices, server-side filtered, paginated)

Auth: xi-api-key header.

TTS models, voices, and the STT parse all run concurrently via asyncio.gather.
"""

from __future__ import annotations

import asyncio

import httpx

from voicedex.config import settings
from voicedex.sync.ai_parser import AIParserError, parse_models_from_docs
from voicedex.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncModel, SyncResult, SyncVoice
from voicedex.sync.language import normalize_languages

_MODELS_URL = "https://api.elevenlabs.io/v1/models"
_VOICES_URL = "https://api.elevenlabs.io/v2/voices"

_STT_MODELS_DOCS_URLS = [
    "https://elevenlabs.io/docs/capabilities/speech-to-text",
]

_VOICE_PAGE_SIZE = 100   # ElevenLabs v2 max is 100
_MAX_VOICE_PAGES = 20    # safety cap; 100 × 20 = 2000 voices ceiling

_GENDER_MAP = {
    "male":       "male",
    "female":     "female",
    "neutral":    "neutral",
    "non-binary": "neutral",
}

_STT_MODELS_GUIDANCE = (
    "Return EVERY callable speech-to-text model id documented (exact API strings). Mark exactly one "
    "is_default=true: the recommended production model. If the docs give a language count without "
    "listing them, use ['*']. streaming=true only for models usable over the realtime/websocket API; "
    "set meta.batch for models usable via the file-upload endpoint. Use canonical capability flags "
    "(word_timestamps, speaker_diarization, language_detection, …) rather than meta for documented features."
)


class ElevenLabsSyncer(ProviderSyncer):
    provider_id = "elevenlabs"
    source = "mixed"

    async def sync(self) -> SyncResult:
        if not settings.elevenlabs_api_key:
            raise ValueError("ELEVENLABS_API_KEY is not set in .env")

        ai_key = settings.anthropic_api_key or None

        models_data, voices_data, (stt_models, stt_notes) = await asyncio.gather(
            self._fetch_models(),
            self._fetch_voices(),
            parse_models_from_docs(
                seed_urls=_STT_MODELS_DOCS_URLS,
                provider_id=self.provider_id,
                model_type="stt",
                guidance=_STT_MODELS_GUIDANCE,
                api_key=ai_key,
            ),
        )

        api_stt_models, tts_models, sts_models = self._parse_models(models_data)
        tts_voices = self._parse_voices(voices_data)

        # If /v1/models ever starts returning STT entries, merge them in
        # (skipping any IDs the AI parser already produced).
        ai_stt_ids = {m.model_id for m in stt_models}
        for api_m in api_stt_models:
            if api_m.model_id not in ai_stt_ids:
                stt_models.append(api_m)

        if stt_notes.get("source") == "cache":
            notes = (
                f"TTS models: {len(tts_models)} from /v1/models. "
                f"STT models: {len(stt_models)} (cache). "
                f"Voices: {len(tts_voices)} from /v2/voices."
            )
        else:
            notes = (
                f"TTS models: {len(tts_models)} from /v1/models. "
                f"STT models: {len(stt_models)} from {len(stt_notes['urls_fetched'])} doc page(s). "
                f"Voices: {len(tts_voices)} from /v2/voices. "
                f"AI: {stt_notes['input_tokens']} in / {stt_notes['output_tokens']} out tokens ({stt_notes['model']})."
            )

        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            tts_voices=tts_voices,
            sts_models=sts_models,
            source=self.source,
            api_urls=[_MODELS_URL, _VOICES_URL],
            docs_urls=_STT_MODELS_DOCS_URLS,
            notes=notes,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_models(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(_MODELS_URL, headers=self._auth_headers())
            resp.raise_for_status()
            return resp.json()

    async def _fetch_voices(self) -> list[dict]:
        voices: list[dict] = []
        next_token: str | None = None

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for _ in range(_MAX_VOICE_PAGES):
                params: dict = {
                    "page_size": _VOICE_PAGE_SIZE,
                    "category":  "premade",  # server-side filter
                }
                if next_token:
                    params["next_page_token"] = next_token

                resp = await client.get(_VOICES_URL, headers=self._auth_headers(), params=params)
                resp.raise_for_status()
                data = resp.json()

                voices.extend(data.get("voices", []))

                if not data.get("has_more", False):
                    break
                next_token = data.get("next_page_token")
                if not next_token:
                    break
            else:
                raise RuntimeError(
                    f"ElevenLabs voice pagination exceeded {_MAX_VOICE_PAGES} pages — possible cursor loop"
                )

        return voices

    def _auth_headers(self) -> dict[str, str]:
        return {"xi-api-key": settings.elevenlabs_api_key}

    def _parse_models(self, data: list[dict]) -> tuple[list[SyncModel], list[SyncModel], list[SyncModel]]:
        """Returns (stt, tts, sts). /v1/models lists models newest/recommended first, so the
        default TTS model is the first GA text-to-speech entry — no hardcoded preference."""
        stt_models: list[SyncModel] = []
        tts_models: list[SyncModel] = []
        sts_models: list[SyncModel] = []

        for m in data:
            languages = normalize_languages([
                lang["language_id"] for lang in (m.get("languages") or []) if lang.get("language_id")
            ])
            alpha = bool(m.get("requires_alpha_access"))
            rates = m.get("model_rates") or {}
            meta = {
                "can_be_finetuned":     m.get("can_be_finetuned"),
                "can_use_speaker_boost": m.get("can_use_speaker_boost"),
                "serves_pro_voices":    m.get("serves_pro_voices"),
                "concurrency_group":    m.get("concurrency_group"),
                "character_cost_multiplier": rates.get("character_cost_multiplier"),
                "max_characters_free_user": m.get("max_characters_request_free_user"),
            }
            common = dict(
                model_id=m["model_id"],
                display_name=m.get("name") or m["model_id"],
                languages=languages,
                streaming=True,
                lifecycle="alpha" if alpha else "ga",
                description=m.get("description"),
                max_text_chars=m.get("maximum_text_length_per_request"),
                capabilities=["style_control"] if m.get("can_use_style") else [],
                interfaces=["http", "websocket"],
                meta={k: v for k, v in meta.items() if v is not None},
            )

            if m.get("can_do_text_to_speech"):
                tts_models.append(SyncModel(type="tts", **common))
            if m.get("can_do_voice_conversion"):
                sts_models.append(SyncModel(type="sts", **{
                    **common, "interfaces": ["http"],
                    "meta": {**common["meta"], "mode": "voice_conversion"},
                }))
            if m.get("can_do_speech_to_text"):
                stt_models.append(SyncModel(type="stt", **{**common, "max_text_chars": None}))

        for models in (tts_models, sts_models):
            default = next((x for x in models if x.lifecycle == "ga"), None)
            if default:
                default.is_default = True
        return stt_models, tts_models, sts_models

    def _parse_voices(self, items: list[dict]) -> list[SyncVoice]:
        voices: list[SyncVoice] = []
        for v in items:
            # Defense in depth — server already filters category=premade.
            if v.get("category") != "premade":
                continue

            labels = v.get("labels") or {}
            verified = v.get("verified_languages") or []
            # Prefer full locales ("en-US") over bare languages; primary label language first.
            locales = [e.get("locale") or e.get("language") for e in verified if e.get("locale") or e.get("language")]
            primary = labels.get("language")
            languages = list(dict.fromkeys(normalize_languages(([primary] if primary else []) + locales)))
            # A bare "en" adds nothing once "en-US" is present.
            languages = [lang for lang in languages if "-" in lang or not any(x.startswith(lang + "-") for x in languages)]

            raw_name = v.get("name") or v["voice_id"]
            name, _, tagline = raw_name.partition(" - ")
            descriptive = labels.get("descriptive") or labels.get("description") or ""
            tags = [t.strip() for t in descriptive.split(",") if t.strip()]

            voices.append(SyncVoice(
                voice_id=v["voice_id"],
                display_name=name.strip() or raw_name,
                gender=_GENDER_MAP.get((labels.get("gender") or "").lower()),
                category="premade",
                languages=languages,
                description=v.get("description"),
                preview_url=v.get("preview_url"),
                accent=labels.get("accent"),
                age=(labels.get("age") or "").replace("_", " ") or None,
                use_cases=[labels["use_case"].replace("_", " ")] if labels.get("use_case") else [],
                tags=tags,
                # Premade voices work with every ElevenLabs TTS model; the API's
                # "high quality" list is a quality hint (and includes retired ids).
                compatible_models=["*"],
                meta={k: val for k, val in {
                    "tagline": tagline.strip() or None,
                    "high_quality_models": v.get("high_quality_base_model_ids") or None,
                    "available_for_tiers": v.get("available_for_tiers") or None,
                }.items() if val},
            ))
        return voices


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = ElevenLabsSyncer()
    try:
        result = await syncer.sync()
    except (ValueError, AIParserError) as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise SystemExit(1)
    except httpx.HTTPStatusError as e:
        print(
            f"\nElevenLabs API error ({e.response.status_code}): {e.response.text[:300]}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        marker = " [default]" if m.is_default else ""
        print(f"  {m.model_id!r:35} {m.display_name!r:35} langs={len(m.languages)}{marker}")
        if m.meta:
            print(f"    meta: {m.meta}")

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        marker = " [default]" if m.is_default else ""
        print(f"  {m.model_id!r:35} {m.display_name!r:35} langs={len(m.languages)}{marker}")

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) — showing first 20 ===")
    for v in result.tts_voices[:20]:
        print(
            f"  {v.voice_id!r:25} {v.display_name!r:20} "
            f"gender={v.gender} accent={v.accent} age={v.age} langs={v.languages}"
        )
    if len(result.tts_voices) > 20:
        print(f"  ... and {len(result.tts_voices) - 20} more")


if __name__ == "__main__":
    asyncio.run(_main())
