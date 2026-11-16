"""
Unreal Speech sync script.

Source: docs
  - TTS model  : AI-parsed from docs (one model: kokoro)
  - TTS voices : AI-parsed from docs (48 voices, 8 languages)
  - STT        : not offered — stt_models=[]

No voice listing REST endpoint exists; voices are documented on the studio page.
Auth: Authorization: Bearer API_KEY
Config: UNREAL_SPEECH_API_KEY (reserved; all data comes from public docs)
"""

from __future__ import annotations

import asyncio
import sys

from naaviq.sync.ai_parser import AIParserError, parse_models_from_docs, parse_voices_from_docs
from naaviq.sync.base import ProviderSyncer, SyncResult

_DOCS_URLS = [
    "https://docs.v8.unrealspeech.com/",   # JS-rendered; content via the Postman collection it embeds
    "https://unrealspeech.com/",
    "https://unrealspeech.com/pricing",
]

_TTS_MODEL_GUIDANCE = (
    "Return every TTS engine/model id the API accepts (e.g. the `Model` request field). "
    "is_default=true for the engine used when none is specified. Per-character pricing from "
    "plan overage rates (per 1M characters) when stated."
)

_VOICES_GUIDANCE = (
    "Return every built-in voice accepted as `VoiceId` by the current (v8) API, using the exact "
    "VoiceId string. Exclude voices labeled legacy. Record any underlying engine voice id in "
    "meta. compatible_models = the engine ids the voice works with."
)


class UnrealSpeechSyncer(ProviderSyncer):
    provider_id = "unrealspeech"
    source = "docs"

    async def sync(self) -> SyncResult:
        (tts_models, tts_notes), (tts_voices, voice_notes) = await asyncio.gather(
            parse_models_from_docs(
                seed_urls=_DOCS_URLS,
                provider_id=self.provider_id,
                model_type="tts",
                guidance=_TTS_MODEL_GUIDANCE,
            ),
            parse_voices_from_docs(
                seed_urls=_DOCS_URLS,
                provider_id=self.provider_id,
                guidance=_VOICES_GUIDANCE,
            ),
        )

        from_cache = (
            isinstance(tts_notes, dict) and tts_notes.get("source") == "cache"
            and isinstance(voice_notes, dict) and voice_notes.get("source") == "cache"
        )
        notes = (
            f"{len(tts_models)} TTS models (cache). {len(tts_voices)} voices (cache)."
            if from_cache else
            f"{len(tts_models)} TTS models. {len(tts_voices)} voices."
        )

        return SyncResult(
            stt_models=[],
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            docs_urls=_DOCS_URLS,
            notes=notes,
        )


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    syncer = UnrealSpeechSyncer()
    try:
        result = await syncer.sync()
    except AIParserError as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        marker = " [default]" if m.is_default else ""
        print(f"  {m.model_id!r:12} {m.display_name!r:20} langs={m.languages}{marker}")

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) ===")
    for v in result.tts_voices:
        print(
            f"  {v.voice_id!r:20} {v.display_name!r:22} "
            f"gender={v.gender or '?':6} langs={v.languages}"
        )

    print(f"\nSource : {result.source}")
    print(f"Notes  : {result.notes}")
    print(f"Fetched: {result.fetched_at}")


if __name__ == "__main__":
    asyncio.run(_main())
