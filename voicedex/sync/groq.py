"""
Groq sync script.

Source: mixed
  - STT/TTS models: GET https://api.groq.com/openai/v1/models (auth). The API describes each model's
                    input/output modalities, upstream creator (`owned_by`), Hugging Face id and — for
                    TTS — per-character pricing, so models are classified from the API itself:
                      output "speech"        → TTS
                      output "transcription" → STT
                    No hardcoded model table: models Groq stops serving drop out automatically.
  - TTS voices    : parsed from docs (no voice-listing API).

Groq hosts third-party models; the creator is recorded in meta.upstream.

Auth: Authorization: Bearer header. Config: GROQ_API_KEY
"""

from __future__ import annotations

import asyncio

import httpx

from voicedex.config import settings
from voicedex.sync.ai_parser import parse_voices_from_docs
from voicedex.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncModel, SyncResult, get_with_retry

_MODELS_URL = "https://api.groq.com/openai/v1/models"

_DOCS_URLS = [
    "https://console.groq.com/docs/text-to-speech/orpheus.md",
    "https://console.groq.com/docs/speech-to-text.md",
    "https://console.groq.com/docs/deprecations.md",
]

_VOICES_GUIDANCE = (
    "Return every built-in TTS voice for the speech models Groq currently serves (exact lowercase "
    "`voice` strings). compatible_models = the exact model ids each voice works with. Record the "
    "upstream model creator in meta.upstream. Exclude voices of shut-down models."
)

# Default = first of these the API actually serves (never a phantom default).
_STT_DEFAULT_PREFERENCE = ["whisper-large-v3", "whisper-large-v3-turbo"]
_TTS_DEFAULT_PREFERENCE = ["canopylabs/orpheus-v1-english"]

# Language words that appear in Groq's model ids/names (provider-stated, not guessed).
_NAME_LANGUAGES = {"english": "en", "arabic": "ar", "saudi": "ar-SA"}


class GroqSyncer(ProviderSyncer):
    provider_id = "groq"
    source = "mixed"

    async def sync(self) -> SyncResult:
        models_data, (tts_voices, voice_notes) = await asyncio.gather(
            self._fetch_models(),
            parse_voices_from_docs(seed_urls=_DOCS_URLS, provider_id=self.provider_id, guidance=_VOICES_GUIDANCE),
        )
        stt_models, tts_models = parse_models(models_data)
        served = {m.model_id for m in tts_models}
        tts_voices = [v for v in tts_voices if set(v.compatible_models) & served]

        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            api_urls=[_MODELS_URL],
            docs_urls=_DOCS_URLS,
            notes=f"{len(stt_models)} STT, {len(tts_models)} TTS from /models; {len(tts_voices)} voices.",
        )

    async def _fetch_models(self) -> list[dict]:
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is not set in .env")
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await get_with_retry(client, _MODELS_URL,
                                        headers={"Authorization": f"Bearer {settings.groq_api_key}"})
            resp.raise_for_status()
            return resp.json().get("data") or []


def parse_models(models_data: list[dict]) -> tuple[list[SyncModel], list[SyncModel]]:
    stt: list[SyncModel] = []
    tts: list[SyncModel] = []
    for m in models_data:
        if not m.get("id") or m.get("active") is False:
            continue
        outputs = set(m.get("output_modalities") or [])
        if "speech" in outputs:
            target, mtype = tts, "tts"
        elif "transcription" in outputs:
            target, mtype = stt, "stt"
        else:
            continue  # LLMs etc.
        target.append(SyncModel(
            model_id=m["id"],
            display_name=m.get("name") or m["id"],
            type=mtype,
            languages=_languages(m),
            streaming=mtype == "tts",  # Groq transcription is file-based; TTS streams audio
            pricing=_pricing(m) if mtype == "tts" else {},
            max_text_chars=m.get("context_window") if mtype == "tts" else None,
            interfaces=["http"],
            meta={k: v for k, v in {
                "upstream": m.get("owned_by"),
                "hugging_face_id": m.get("hugging_face_id"),
                "model_card": m.get("model_card"),
                "batch": True if mtype == "stt" else None,
            }.items() if v is not None},
        ))
    for models, pref in ((stt, _STT_DEFAULT_PREFERENCE), (tts, _TTS_DEFAULT_PREFERENCE)):
        ids = {x.model_id for x in models}
        default = next((p for p in pref if p in ids), None)
        for x in models:
            x.is_default = x.model_id == default
    return stt, tts


def _languages(m: dict) -> list[str]:
    text = f"{m.get('id', '')} {m.get('name', '')}".lower()
    found = [code for word, code in _NAME_LANGUAGES.items() if word in text]
    if "ar-SA" in found:
        found = [c for c in found if c != "ar"]
    if found:
        return found
    if "whisper" in text and not text.endswith(".en"):
        return ["*"]  # Whisper is multilingual (~99 languages), not enumerated by the API
    return []


def _pricing(m: dict) -> dict:
    """Groq reports TTS input pricing per character as `pricing.prompt` (string USD)."""
    raw = (m.get("pricing") or {}).get("prompt")
    try:
        price = float(raw)
    except (TypeError, ValueError):
        return {}
    if price <= 0:
        return {}
    return {"unit": "character", "price_usd": price, "source_url": _MODELS_URL,
            "notes": "From Groq /models API (pricing.prompt)"}


async def _main() -> None:
    result = await GroqSyncer().sync()
    for m in result.stt_models + result.tts_models:
        print(f"  {m.type} {m.model_id!r:40} default={m.is_default} langs={m.languages} pricing={m.pricing}")
    print(f"{len(result.tts_voices)} voices. {result.notes}")


if __name__ == "__main__":
    asyncio.run(_main())
