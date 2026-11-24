"""
Sarvam sync script.

Source: docs
  - STT models : AI-parsed from docs.sarvam.ai (every STT product/API)
  - TTS models : AI-parsed from docs.sarvam.ai (Bulbul family)
    + Instant Voice Cloning (beta) — a separate /voices/clone API with no model
      parameter; catalogued as TTS model "instant-voice-cloning"
  - TTS voices : AI-parsed from docs.sarvam.ai (speaker enum in the TTS API reference)

Indian AI provider specializing in Indian languages. Models, voices and deprecation
status all come from documentation: the only list API (GET /v2/models) covers Token
Factory LLMs, not speech, and GET /voices lists the caller's *private* cloned voices
(never published). Checked 2026-11-16.

Extraction is done by Claude Code into .sync-cache/ (see CLAUDE.md); SARVAM_API_KEY is unused.

STT models, TTS models, and TTS voices parse concurrently via asyncio.gather.
"""

from __future__ import annotations

import asyncio
import sys

from voicedex.sync.ai_parser import AIParserError, parse_models_from_docs, parse_voices_from_docs
from voicedex.sync.base import ProviderSyncer, SyncResult

_LLMS = "https://docs.sarvam.ai/api/llms.txt"  # index of current .md pages

_STT_DOCS = [
    "https://docs.sarvam.ai/api-reference/speech-to-text/transcribe",
    "https://docs.sarvam.ai/api/getting-started/models",
    "https://docs.sarvam.ai/api/getting-started/pricing",
    _LLMS,
]

_TTS_DOCS = [
    "https://docs.sarvam.ai/api-reference/text-to-speech/convert",
    "https://docs.sarvam.ai/api/api-guides-tutorials/voice-cloning/overview",
    "https://docs.sarvam.ai/api-reference/voice-cloning/clone",
    "https://docs.sarvam.ai/api/getting-started/models",
    "https://docs.sarvam.ai/api/getting-started/pricing",
    _LLMS,
]

_VOICES_DOCS = [
    "https://docs.sarvam.ai/api-reference/text-to-speech/convert",
    _LLMS,  # → text-to-speech/voices.md
]

_COMMON = (
    "Use exact model_id strings. Exactly one is_default per type: the model the docs call "
    "latest/recommended (record the API's fallback model in meta if different). Exclude models the "
    "docs call deprecated with no date; set eol_date only when a date is published (never guess). "
    "Languages are BCP-47 with region (hi-IN, ta-IN, …). Pricing is INR: put it in "
    "meta.pricing_inr with the source URL unless an explicit USD price is published."
)
_STT_GUIDANCE = (
    "Return every Sarvam speech-to-text model across all of its STT products and APIs (each product's "
    "model ids, moving aliases with meta.alias_of → the dated snapshot). streaming=true only for "
    "models usable over the WebSocket API; meta.batch for the batch/REST APIs. " + _COMMON
)
_TTS_GUIDANCE = (
    "Return every Sarvam text-to-speech model (Bulbul family), plus Instant Voice Cloning as model_id "
    "'instant-voice-cloning' (separate endpoint, no model parameter; capability voice_cloning). " + _COMMON
)
_VOICES_GUIDANCE = (
    "Return every speaker the TTS API accepts (exact speaker string). compatible_models = the model "
    "ids each speaker works with. Gender only when the docs state it (never infer from names). "
    "languages = the locales the speaker's model(s) support."
)


class SarvamSyncer(ProviderSyncer):
    provider_id = "sarvam"
    source = "docs"

    async def sync(self) -> SyncResult:
        from voicedex.config import settings
        ai_key = settings.anthropic_api_key or None

        (stt_models, stt_notes), (tts_models, tts_notes), (tts_voices, voice_notes) = (
            await asyncio.gather(
                parse_models_from_docs(
                    seed_urls=_STT_DOCS,
                    provider_id=self.provider_id,
                    model_type="stt",
                    guidance=_STT_GUIDANCE,
                    api_key=ai_key,
                ),
                parse_models_from_docs(
                    seed_urls=_TTS_DOCS,
                    provider_id=self.provider_id,
                    model_type="tts",
                    guidance=_TTS_GUIDANCE,
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

        from_cache = any(n.get("source") == "cache" for n in [stt_notes, tts_notes, voice_notes])
        if from_cache:
            notes = (
                f"STT models: {len(stt_models)} (cache). "
                f"TTS models: {len(tts_models)} (cache). "
                f"TTS voices: {len(tts_voices)} (cache)."
            )
        else:
            total_in  = stt_notes["input_tokens"]  + tts_notes["input_tokens"]  + voice_notes["input_tokens"]
            total_out = stt_notes["output_tokens"] + tts_notes["output_tokens"] + voice_notes["output_tokens"]
            notes = (
                f"STT models: {len(stt_models)} from {len(stt_notes['urls_fetched'])} page(s). "
                f"TTS models: {len(tts_models)} from {len(tts_notes['urls_fetched'])} page(s). "
                f"TTS voices: {len(tts_voices)} from {len(voice_notes['urls_fetched'])} page(s). "
                f"AI: {total_in} in / {total_out} out tokens ({stt_notes['model']})."
            )

        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            docs_urls=list(dict.fromkeys(_STT_DOCS + _TTS_DOCS + _VOICES_DOCS)),
            notes=notes,
        )


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    syncer = SarvamSyncer()
    try:
        result = await syncer.sync()
    except AIParserError as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        marker = " [default]" if m.is_default else ""
        print(f"  {m.model_id!r:25} {m.display_name!r:30} langs={len(m.languages)}{marker}")
        if m.meta:
            print(f"    meta: {m.meta}")

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        marker = " [default]" if m.is_default else ""
        print(f"  {m.model_id!r:25} {m.display_name!r:30} langs={len(m.languages)}{marker}")
        if m.meta:
            print(f"    meta: {m.meta}")

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) ===")
    for v in result.tts_voices:
        print(
            f"  {v.voice_id!r:15} {v.display_name!r:15} "
            f"gender={v.gender} langs={v.languages} meta={v.meta}"
        )

    if result.notes:
        print(f"\n=== Notes ===\n  {result.notes}")


if __name__ == "__main__":
    asyncio.run(_main())
