"""
Speechmatics sync script.

Source: docs
  - STT models: AI-parsed from docs — enhanced, default, medical
  - TTS: skipped — TTS is in preview, English-only, no stable list endpoint
  - tts_models=[], tts_voices=[]

STT is the core product: 55+ languages, batch + real-time WebSocket.

Auth: SPEECHMATICS_API_KEY env var (not needed for docs parsing).
"""

from __future__ import annotations

import asyncio

from naaviq.config import settings  # noqa: F401 — triggers load_dotenv() for ANTHROPIC_API_KEY
from naaviq.sync.ai_parser import notes_to_str, parse_models_from_docs
from naaviq.sync.base import ProviderSyncer, SyncResult

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
        return SyncResult(
            stt_models=stt_models,
            tts_models=[],
            tts_voices=[],
            source=self.source,
            docs_urls=_STT_SEED_URLS,
            notes=notes_to_str(notes),
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
