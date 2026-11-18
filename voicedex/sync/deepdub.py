"""
Deepdub — eTTS (emotive text-to-speech) models over REST and WebSocket, with voice cloning and accent control.

Source: docs (docs.deepdub.ai; index at https://docs.deepdub.ai/llms.txt). Model ids are listed in the SDK
reference; supported locales, formats and sample rates in the REST API reference. Stock voices are the curated
voice presets page (the full voice library is sales-only; GET /voice-prompts lists only an account's private
prompts and needs a key). No public per-unit pricing — packages are sold through sales.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOCS = "https://docs.deepdub.ai/"


class DeepdubSyncer(DocsOnlySyncer):
    provider_id = "deepdub"
    tts_docs = [
        _DOCS + "sdk.md",
        _DOCS + "sdk-javascript.md",
        _DOCS + "api-reference/tts/generate-and-stream-tts-audio.md",
        _DOCS + "api-reference/websocket/overview.md",
        _DOCS + "api-reference/websocket/streaming.md",
    ]
    voices_docs = [_DOCS + "voice-presets.md"]
    tts_guidance = (
        "Return every model id in the SDK 'Available Models' table. Languages are the locale table in the REST "
        "API reference; formats and sample rates from the REST and WebSocket references. Default only the model "
        "the docs mark as default. No prices unless Deepdub publishes a per-unit rate."
    )
    voices_guidance = (
        "Return every voice preset row (Voice Prompt ID is the exact voice_id); language from the section "
        "heading, gender from the M/F column, speaker and speaking style in meta."
    )
