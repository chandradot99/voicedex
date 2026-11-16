"""
AssemblyAI sync script.

Source: docs — no API key needed.
  - STT models: pre-recorded (batch) and streaming speech models
  - TTS models + voices: AssemblyAI TTS (launched 2026)
"""

from __future__ import annotations

import asyncio

from naaviq.config import settings  # noqa: F401 — triggers load_dotenv() for ANTHROPIC_API_KEY
from naaviq.sync.ai_parser import notes_to_str, parse_models_from_docs, parse_voices_from_docs
from naaviq.sync.base import ProviderSyncer, SyncResult

_STT_URLS = [
    "https://www.assemblyai.com/docs/getting-started/models",
    "https://www.assemblyai.com/docs/pre-recorded-audio/select-the-speech-model",
    "https://www.assemblyai.com/docs/streaming/select-the-speech-model",
    "https://www.assemblyai.com/docs/pre-recorded-audio/supported-languages",
    "https://www.assemblyai.com/pricing",
]
_TTS_URLS = [
    "https://www.assemblyai.com/docs/tts/voices",
    "https://www.assemblyai.com/docs/tts/connect-parameters",
    "https://www.assemblyai.com/docs/tts/api-reference/http-api/overview",
    "https://www.assemblyai.com/docs/tts/limits",
    "https://www.assemblyai.com/docs/getting-started/models",
]

_STT_GUIDANCE = (
    "Return every speech model id accepted by `speech_model` on the pre-recorded and streaming APIs "
    "(an id valid on both is ONE model with streaming=true and meta.batch=true; per-API prices as "
    "variants). is_default=true for the model used when `speech_model` is omitted on the streaming "
    "API. Models labeled Preview are lifecycle beta. Per-hour pricing."
)
_TTS_GUIDANCE = (
    "Return every text-to-speech model id. is_default=true for the recommended one. Per-character "
    "pricing (convert per-1M-character prices)."
)
_VOICES_GUIDANCE = (
    "Return every built-in TTS voice (exact voice id), with gender/language/accent only where stated "
    "and compatible_models = the TTS model ids it works with."
)


class AssemblyAISyncer(ProviderSyncer):
    provider_id = "assemblyai"
    source = "docs"

    async def sync(self) -> SyncResult:
        (stt_models, notes), (tts_models, _), (tts_voices, _) = await asyncio.gather(
            parse_models_from_docs(seed_urls=_STT_URLS, provider_id=self.provider_id,
                                   model_type="stt", guidance=_STT_GUIDANCE),
            parse_models_from_docs(seed_urls=_TTS_URLS, provider_id=self.provider_id,
                                   model_type="tts", guidance=_TTS_GUIDANCE),
            parse_voices_from_docs(seed_urls=_TTS_URLS, provider_id=self.provider_id,
                                   guidance=_VOICES_GUIDANCE),
        )
        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            docs_urls=_STT_URLS + [u for u in _TTS_URLS if u not in _STT_URLS],
            notes=notes_to_str(notes),
        )


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    syncer = AssemblyAISyncer()
    result = await syncer.sync()

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        stream_label = "streaming" if m.streaming else "batch   "
        print(
            f"  {m.model_id!r:38} [{stream_label}] "
            f"langs={m.languages} is_default={m.is_default}"
        )

    print(f"\nSource: {result.source}")
    print(f"Fetched at: {result.fetched_at}")
    if result.notes:
        print(f"\nNotes: {result.notes}")


if __name__ == "__main__":
    asyncio.run(_main())
