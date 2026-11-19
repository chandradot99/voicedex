"""
Speechmatics sync script.

Source: docs
  - STT models: AI-parsed from docs — enhanced, default, medical
  - TTS: docs-parsed. The API has no model parameter (a request names a voice in the URL path), so the
    catalog carries one model for the service; voices from the quickstart's voice table.

STT is the core product: 55+ languages, batch + real-time WebSocket.

Auth: SPEECHMATICS_API_KEY env var (not needed for docs parsing).
"""

from __future__ import annotations

import asyncio

from voicedex.config import settings  # noqa: F401 — triggers load_dotenv() for ANTHROPIC_API_KEY
from voicedex.sync.ai_parser import notes_to_str, parse_models_from_docs, parse_voices_from_docs
from voicedex.sync.base import ProviderSyncer, SyncResult

_STT_SEED_URLS = [
    "https://docs.speechmatics.com/speech-to-text/models",
    "https://docs.speechmatics.com/speech-to-text/languages",
    "https://docs.speechmatics.com/speech-to-text/batch/input",
    "https://docs.speechmatics.com/speech-to-text/realtime/input",
    "https://www.speechmatics.com/pricing",
]
_STT_MODEL_GUIDANCE = (
    "Return EVERY Speechmatics STT model id accepted by the `model` parameter (the old "
    "`operating_point` is deprecated). is_default=true for the model used when `model` is unset. "
    "Domain variants selected by a separate parameter (e.g. domain=medical) are not separate models — "
    "record them in meta. Enumerate languages per model; per-hour pricing with batch/realtime variants."
)

_TTS_SEED_URLS = [
    "https://docs.speechmatics.com/text-to-speech/quickstart",
    "https://www.speechmatics.com/pricing",
]
_TTS_MODEL_GUIDANCE = (
    "The TTS API has no model parameter: a request names a voice in the URL path. Return one model for the "
    "Speechmatics TTS service (meta.no_model_parameter=true) with the documented output formats, sample rates, "
    "streaming behaviour, lifecycle wording and the per-character price from the pricing page (with free tier). "
    "Leave languages empty (filled from the voices)."
)
_TTS_VOICE_GUIDANCE = (
    "Every voice id documented for the TTS API (the exact path segment), with gender, accent and language as "
    "documented. compatible_models=['*']."
)


class SpeechmaticsSyncer(ProviderSyncer):
    provider_id = "speechmatics"
    source = "docs"

    async def sync(self) -> SyncResult:
        stt_models, notes = await parse_models_from_docs(
            seed_urls=_STT_SEED_URLS,
            provider_id=self.provider_id,
            model_type="stt",
            guidance=_STT_MODEL_GUIDANCE,
        )
        tts_models, tts_notes = await parse_models_from_docs(
            seed_urls=_TTS_SEED_URLS,
            provider_id=self.provider_id,
            model_type="tts",
            guidance=_TTS_MODEL_GUIDANCE,
        )
        tts_voices, voice_notes = await parse_voices_from_docs(
            seed_urls=_TTS_SEED_URLS,
            provider_id=self.provider_id,
            guidance=_TTS_VOICE_GUIDANCE,
        )
        langs = sorted({lang for v in tts_voices for lang in v.languages})
        for m in tts_models:
            if not m.languages:
                m.languages = langs
        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            docs_urls=list(dict.fromkeys(_STT_SEED_URLS + _TTS_SEED_URLS)),
            notes=" ".join(filter(None, [notes_to_str(notes), notes_to_str(tts_notes), notes_to_str(voice_notes)])),
        )


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    syncer = SpeechmaticsSyncer()
    result = await syncer.sync()

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        print(
            f"  {m.model_id!r:15} {m.display_name!r:20} "
            f"langs={m.languages} is_default={m.is_default}"
        )

    print(f"\nSource: {result.source}")
    print(f"Fetched at: {result.fetched_at}")
    if result.notes:
        print(f"\nNotes: {result.notes}")


if __name__ == "__main__":
    asyncio.run(_main())
