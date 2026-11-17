"""
IBM Watson Speech sync script.

Source: api
  - STT models: GET {IBM_STT_URL}/v1/models
      kept:    large speech models (id = bare locale, e.g. "en-US"; GA since 2024-08-23)
               next-generation "{locale}_Multimedia" (16 kHz) / "{locale}_Telephony" (8 kHz)
      dropped: previous-generation *_BroadbandModel / *_NarrowbandModel — discontinued 2023-08-01
               (the API still lists them; requests are remapped to next-gen models)
  - TTS voices: GET {IBM_TTS_URL}/v1/voices
  - TTS models: IBM has no model parameter — the voice name selects the engine. The catalog
      groups voices into their documented technology tiers (Natural / Expressive / Enhanced
      neural "V3Voice"); the tier ids (ibm-natural, …) are catalog groupings, not API params.
      V1/V2 voice names are withdrawn aliases that IBM remaps to V3 — not published.

IBM_TTS_URL / IBM_STT_URL must be the *instance* URLs from the service's Manage page
(https://api.<region>.<service>.watson.cloud.ibm.com/instances/<id>); a bare regional URL → 403.

Capabilities come from each model's `supported_features` (speaker_labels, custom_language_model)
plus features IBM documents for every current model (timestamps, profanity filter, SSML).
Docs: https://cloud.ibm.com/docs/speech-to-text?topic=speech-to-text-summary
      https://cloud.ibm.com/docs/text-to-speech?topic=text-to-speech-voices

Auth: HTTP Basic, username "apikey", password = the service API key.
"""

from __future__ import annotations

import asyncio

import httpx

from voicedex.config import settings
from voicedex.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncModel, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.language import normalize_languages

_TTS_VOICES_PATH = "/v1/voices"
_STT_MODELS_PATH = "/v1/models"

_DOCS_URLS = [
    "https://cloud.ibm.com/docs/speech-to-text?topic=speech-to-text-models-large-speech-languages",
    "https://cloud.ibm.com/docs/speech-to-text?topic=speech-to-text-models-ng",
    "https://cloud.ibm.com/docs/speech-to-text?topic=speech-to-text-models",
    "https://cloud.ibm.com/docs/text-to-speech?topic=text-to-speech-voices",
]

# Voice-name suffix → (catalog model id, display name, description). Order = display order.
_VOICE_TIERS: dict[str, tuple[str, str, str]] = {
    "Natural":    ("ibm-natural",    "IBM Natural voices",
                   "IBM's most natural-sounding voice tier (voice names ending in 'Natural')."),
    "Expressive": ("ibm-expressive", "IBM Expressive neural voices",
                   "Conversational voices with speaking styles and emphasis (names ending in 'Expressive')."),
    "V3Voice":    ("ibm-neural",     "IBM Enhanced neural voices",
                   "Enhanced neural (V3) voices; the service default voice is en-US_MichaelV3Voice."),
}
# Service default when no voice is given: en-US_MichaelV3Voice → the enhanced-neural tier.
_DEFAULT_TTS_TIER = "V3Voice"
# Features documented for every Expressive voice (speaking styles, emphasis).
_TIER_CAPS = {"Expressive": ["style_control"]}

# IBM pseudo-locales that aren't valid BCP-47.
_LOCALE_FIX = {"en-WW": "en", "ar-MS": "ar", "es-LA": "es-419"}

# Documented for all current-generation STT models.
_STT_BASE_CAPS = ["word_timestamps", "profanity_filter"]
# Docs: speaker_labels is Beta on large speech models, GA on next-gen.
_BETA_FEATURES = {"lsm": ["speaker_labels"]}
# Next-gen models IBM labels Beta.
_BETA_MODELS = {"en-WW_Medical_Telephony"}
# IBM's migration notice: en-US_Multimedia replaces the removed en-US_BroadbandModel as the default.
_DEFAULT_STT_MODEL = "en-US_Multimedia"

_GENDER_MAP = {"male": "male", "female": "female"}


class IBMSyncer(ProviderSyncer):
    provider_id = "ibm"
    source = "api"

    async def sync(self) -> SyncResult:
        tts_key = settings.ibm_tts_api_key
        stt_key = settings.ibm_stt_api_key
        if not tts_key:
            raise ValueError("IBM_TTS_API_KEY is not set in .env")
        if not stt_key:
            raise ValueError("IBM_STT_API_KEY is not set in .env")

        tts_url = settings.ibm_tts_url.rstrip("/") + _TTS_VOICES_PATH
        stt_url = settings.ibm_stt_url.rstrip("/") + _STT_MODELS_PATH
        voices_raw, models_raw = await asyncio.gather(
            self._fetch(tts_url, tts_key), self._fetch(stt_url, stt_key))

        raw_voices = voices_raw.get("voices") or []
        tts_voices = self._parse_voices(raw_voices)
        tts_models = self._derive_tts_models(raw_voices)
        stt_models = self._parse_stt_models(models_raw.get("models") or [])

        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            # Instance ids are account-specific — publish the generic regional form.
            api_urls=[
                "https://api.<region>.text-to-speech.watson.cloud.ibm.com/instances/<id>" + _TTS_VOICES_PATH,
                "https://api.<region>.speech-to-text.watson.cloud.ibm.com/instances/<id>" + _STT_MODELS_PATH,
            ],
            docs_urls=_DOCS_URLS,
            notes=(f"TTS: {len(tts_voices)} voices in {len(tts_models)} tiers. "
                   f"STT: {len(stt_models)} large-speech + next-gen models."),
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch(self, url: str, api_key: str) -> dict:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, auth=("apikey", api_key)) as client:
            resp = await get_with_retry(client, url)
            if resp.status_code == 403:
                raise ValueError(
                    f"IBM returned 403 for {url.split('/instances')[0]} — IBM_TTS_URL/IBM_STT_URL must be the "
                    "instance URL from the service's Manage page (…/instances/<id>), in the instance's region.")
            resp.raise_for_status()
            return resp.json()

    def _parse_voices(self, voices: list[dict]) -> list[SyncVoice]:
        result = []
        for v in voices:
            name: str = v.get("name", "")
            tier = _voice_tier(name)
            if not tier:
                continue  # V1/V2 names: withdrawn aliases remapped to V3 by IBM
            lang = _locale(v.get("language", ""))
            result.append(SyncVoice(
                voice_id=name,
                display_name=_voice_display_name(name),
                gender=_GENDER_MAP.get((v.get("gender") or "").lower()),
                category="premade",
                languages=[lang] if lang else [],
                description=v.get("description"),
                compatible_models=[_VOICE_TIERS[tier][0]],
            ))
        return result

    def _derive_tts_models(self, voices: list[dict]) -> list[SyncModel]:
        tier_langs: dict[str, set[str]] = {}
        tier_pron: dict[str, bool] = {}
        for v in voices:
            tier = _voice_tier(v.get("name", ""))
            if not tier:
                continue
            langs = tier_langs.setdefault(tier, set())
            if lang := _locale(v.get("language", "")):
                langs.add(lang)
            if (v.get("supported_features") or {}).get("custom_pronunciation"):
                tier_pron[tier] = True

        models = []
        for tier, (model_id, display_name, description) in _VOICE_TIERS.items():
            if tier not in tier_langs:
                continue
            caps = ["ssml", *_TIER_CAPS.get(tier, [])]
            if tier_pron.get(tier):
                caps.append("phoneme_input")  # custom pronunciation via IPA / IBM SPR
            models.append(SyncModel(
                model_id=model_id,
                display_name=display_name,
                type="tts",
                languages=sorted(tier_langs[tier]),
                streaming=True,
                is_default=tier == _DEFAULT_TTS_TIER,
                description=description,
                capabilities=sorted(caps),
                interfaces=["http", "websocket"],
                meta={"catalog_grouping": True,
                      "note": "IBM selects the engine by voice name; there is no model parameter."},
            ))
        return models

    def _parse_stt_models(self, models: list[dict]) -> list[SyncModel]:
        result = []
        for m in models:
            name: str = m.get("name", "")
            gen = _stt_generation(name)
            if gen is None:
                continue
            features = {k for k, on in (m.get("supported_features") or {}).items() if on}
            caps = list(_STT_BASE_CAPS)
            if "speaker_labels" in features:
                caps.append("speaker_diarization")
            if "custom_language_model" in features:
                caps.append("custom_vocabulary")
            meta: dict = {"generation": "large_speech_model" if gen == "lsm" else "next_generation"}
            if "low_latency" in features:
                meta["low_latency"] = True
            beta = [f for f in _BETA_FEATURES.get(gen, []) if f in features]
            if beta:
                meta["beta_features"] = beta

            lang = _locale(m.get("language", ""))
            result.append(SyncModel(
                model_id=name,
                display_name=_stt_display_name(name),
                type="stt",
                languages=[lang] if lang else [],
                streaming=True,
                is_default=name == _DEFAULT_STT_MODEL,
                lifecycle="beta" if name in _BETA_MODELS else "ga",
                description=m.get("description"),
                sample_rates_hz=[m["rate"]] if m.get("rate") else [],
                capabilities=sorted(caps),
                interfaces=["http", "websocket"],
                meta={**meta, "parent_model_id": "ibm-large-speech" if gen == "lsm" else f"ibm-{gen}"},
            ))
        return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _locale(code: str) -> str | None:
    if not code:
        return None
    return normalize_languages([_LOCALE_FIX.get(code, code)])[0]


def _voice_tier(name: str) -> str | None:
    for suffix in _VOICE_TIERS:
        if name.endswith(suffix):
            return suffix
    return None


def _stt_generation(name: str) -> str | None:
    """'lsm' | 'multimedia' | 'telephony' | None (previous-generation, discontinued)."""
    if "Broadband" in name or "Narrowband" in name:
        return None
    if "_" not in name:
        return "lsm"
    if name.endswith("_Multimedia"):
        return "multimedia"
    if name.endswith("_Telephony"):
        return "telephony"
    return None


def _voice_display_name(name: str) -> str:
    # "en-US_AllisonExpressive" → "Allison"
    after_lang = name.split("_", 1)[-1]
    for suffix in _VOICE_TIERS:
        if after_lang.endswith(suffix):
            return after_lang[: -len(suffix)]
    return after_lang


def _stt_display_name(name: str) -> str:
    # "en-US" → "en-US Large Speech Model"; "en-WW_Medical_Telephony" → "en-WW Medical Telephony"
    if "_" not in name:
        return f"{name} Large Speech Model"
    return name.replace("_", " ")


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    try:
        result = await IBMSyncer().sync()
    except (ValueError, httpx.HTTPStatusError) as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        print(f"  {m.model_id!r:30} {m.languages} {m.capabilities}{' [default]' if m.is_default else ''}")
    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        print(f"  {m.model_id!r:18} langs={len(m.languages)}{' [default]' if m.is_default else ''}")
    print(f"\n=== TTS Voices ({len(result.tts_voices)}) ===")
    for v in result.tts_voices:
        print(f"  {v.voice_id!r:30} {v.languages} {v.gender} {v.compatible_models}")
    print(f"\nNotes  : {result.notes}")


if __name__ == "__main__":
    asyncio.run(_main())
