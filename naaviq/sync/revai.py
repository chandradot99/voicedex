"""
Rev AI sync script.

Source: docs — STT models (transcribers) parsed from public docs; no API key needed.
Rev AI is STT-only. Human transcription (`human`) is not an AI model and is excluded.
"""

from __future__ import annotations

import asyncio

from naaviq.config import settings  # noqa: F401 — triggers load_dotenv() for ANTHROPIC_API_KEY
from naaviq.sync.ai_parser import notes_to_str, parse_models_from_docs
from naaviq.sync.base import ProviderSyncer, SyncResult

_SEED_URLS = [
    "https://docs.rev.ai/api/asynchronous/transcribers/",
    "https://docs.rev.ai/api/asynchronous/changelog.md",
    "https://docs.rev.ai/api/streaming/transcribers.md",
    "https://docs.rev.ai/api/features.md",
    "https://docs.rev.ai/api/global-deployments.md",
    "https://www.rev.ai/pricing",
]
_MODEL_GUIDANCE = (
    "Return every active AI transcriber id (exact `transcriber` values). Exclude human "
    "transcription and anything the changelog marks deprecated/sunset. is_default=true for the "
    "transcriber used when none is specified. Languages: batch superset in `languages`, the "
    "streaming subset in meta.streaming_languages."
)


class RevAISyncer(ProviderSyncer):
    provider_id = "revai"
    source = "docs"

    async def sync(self) -> SyncResult:
        stt_models, notes = await parse_models_from_docs(
            seed_urls=_SEED_URLS,
            provider_id=self.provider_id,
            model_type="stt",
            guidance=_MODEL_GUIDANCE,
        )
        return SyncResult(
            stt_models=stt_models,
            tts_models=[],
            tts_voices=[],
            source=self.source,
            docs_urls=_SEED_URLS,
            notes=notes_to_str(notes),
        )


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    syncer = RevAISyncer()
    result = await syncer.sync()

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        stream_label = "streaming" if m.streaming else "batch   "
        print(
            f"  {m.model_id!r:12} [{stream_label}] "
            f"langs={m.languages} is_default={m.is_default}"
        )

    print(f"\nSource: {result.source}")
    print(f"Fetched at: {result.fetched_at}")
    if result.notes:
        print(f"\nNotes: {result.notes}")


if __name__ == "__main__":
    asyncio.run(_main())
