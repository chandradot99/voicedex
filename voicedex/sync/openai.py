"""
OpenAI sync script.

Source: docs — no API key needed.
  - TTS models : classic /v1/audio/speech line (deprecated 2026, still callable until EOL)
  - STT models : transcription models (batch + realtime transcription)
  - STS models : realtime / live speech-to-speech models (gpt-realtime-*, gpt-live-*, gpt-audio-*)
  - Voices     : built-in voices, mapped to the TTS and STS models they work with

Models that are deprecated but still callable are kept with `eol_date` set (CLAUDE.md policy).
"""

from __future__ import annotations

import asyncio
import sys

from voicedex.config import settings
from voicedex.sync.ai_parser import AIParserError, parse_models_from_docs, parse_voices_from_docs
from voicedex.sync.base import ProviderSyncer, SyncResult

_MODELS_DOCS = [
    "https://developers.openai.com/api/docs/models/all",
    "https://developers.openai.com/api/docs/deprecations",
    "https://developers.openai.com/api/docs/guides/speech-to-text",
    "https://developers.openai.com/api/docs/guides/realtime-conversations",
]

_VOICES_DOCS = [
    "https://developers.openai.com/api/docs/guides/text-to-speech",
    "https://developers.openai.com/api/docs/guides/realtime-conversations",
    "https://developers.openai.com/api/docs/guides/live-conversations",
]

_COMMON = (
    "Include deprecated models that are still callable, with eol_date = the announced shutdown "
    "date and meta.replacement; exclude models already shut down. Exactly one is_default per type: "
    "the model the docs recommend for new applications. Use per-minute or per-token audio pricing "
    "as published (token prices: audio input as the base price, other token classes as variants)."
)
_TTS_GUIDANCE = "Return every text-to-speech model for the /v1/audio/speech endpoint. " + _COMMON
_STT_GUIDANCE = (
    "Return every speech-to-text / transcription model (batch transcriptions endpoint and realtime "
    "transcription). streaming=true only for models usable over a realtime/websocket session. " + _COMMON
)
_STS_GUIDANCE = (
    "Return every realtime / live speech-to-speech model (audio in, audio out), type='sts'. " + _COMMON
)
_VOICES_GUIDANCE = (
    "Return every built-in voice (exact lowercase API string). compatible_models = the exact TTS and "
    "speech-to-speech model ids each voice works with, per the docs. Gender/accent only when the docs "
    "state them."
)


class OpenAISyncer(ProviderSyncer):
    provider_id = "openai"
    source = "docs"

    async def sync(self) -> SyncResult:
        ai_key = settings.anthropic_api_key or None

        (tts_models, tts_notes), (stt_models, stt_notes), (sts_models, _), (tts_voices, voice_notes) = (
            await asyncio.gather(
                parse_models_from_docs(
                    seed_urls=_MODELS_DOCS,
                    provider_id=self.provider_id,
                    model_type="tts",
                    guidance=_TTS_GUIDANCE,
                    api_key=ai_key,
                ),
                parse_models_from_docs(
                    seed_urls=_MODELS_DOCS,
                    provider_id=self.provider_id,
                    model_type="stt",
                    guidance=_STT_GUIDANCE,
                    api_key=ai_key,
                ),
                parse_models_from_docs(
                    seed_urls=_MODELS_DOCS,
                    provider_id=self.provider_id,
                    model_type="sts",
                    guidance=_STS_GUIDANCE,
                    api_key=ai_key,
                ),
                parse_voices_from_docs(
                    seed_urls=_VOICES_DOCS,
                    provider_id=self.provider_id,
                    guidance=_VOICES_GUIDANCE,
                    api_key=ai_key,
                ),
            )
        )

        from_cache = any(n.get("source") == "cache" for n in [tts_notes, stt_notes, voice_notes])
        if from_cache:
            notes = (
                f"TTS models: {len(tts_models)} (cache). STS models: {len(sts_models)} (cache). "
                f"STT models: {len(stt_models)} (cache). "
                f"TTS voices: {len(tts_voices)} (cache)."
            )
        else:
            total_in  = tts_notes["input_tokens"]  + stt_notes["input_tokens"]  + voice_notes["input_tokens"]
            total_out = tts_notes["output_tokens"] + stt_notes["output_tokens"] + voice_notes["output_tokens"]
            notes = (
                f"TTS models: {len(tts_models)} from {len(tts_notes['urls_fetched'])} page(s). "
                f"STT models: {len(stt_models)} from {len(stt_notes['urls_fetched'])} page(s). "
                f"TTS voices: {len(tts_voices)} from {len(voice_notes['urls_fetched'])} page(s). "
                f"AI: {total_in} in / {total_out} out tokens ({tts_notes['model']})."
            )

        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            sts_models=sts_models,
            tts_voices=tts_voices,
            source=self.source,
            docs_urls=list(dict.fromkeys(_MODELS_DOCS + _VOICES_DOCS)),
            notes=notes,
        )


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    syncer = OpenAISyncer()
    try:
        result = await syncer.sync()
    except AIParserError as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        marker = " [default]" if m.is_default else ""
        print(f"  {m.model_id!r:30} {m.display_name!r:30} langs={m.languages}{marker}")
        if m.meta:
            print(f"    meta: {m.meta}")

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        marker = " [default]" if m.is_default else ""
        print(f"  {m.model_id!r:30} {m.display_name!r:30} langs={m.languages}{marker}")
        if m.meta:
            print(f"    meta: {m.meta}")

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) ===")
    for v in result.tts_voices:
        print(
            f"  {v.voice_id!r:10} {v.display_name!r:12} "
            f"gender={v.gender} langs={v.languages} meta={v.meta}"
        )

    if result.notes:
        print(f"\n=== Notes ===\n  {result.notes}")


if __name__ == "__main__":
    asyncio.run(_main())
