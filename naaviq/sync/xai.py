"""
xAI — Grok Voice: realtime speech-to-speech, speech-to-text, text-to-speech.

Source: docs (docs.x.ai). The voices endpoint (GET api.x.ai/v1/tts/voices) needs a key, and
creating one requires prepaid credit — so voices come from the docs too. With an XAI_API_KEY this
could move to the API (backlog).
"""

from naaviq.sync.docs_only import DocsOnlySyncer

_BASE = "https://docs.x.ai/developers/model-capabilities/audio/"
_DOCS = [
    "https://docs.x.ai/llms.txt",
    _BASE + "voice.md",
    "https://docs.x.ai/developers/models",
]


class XAISyncer(DocsOnlySyncer):
    provider_id = "xai"
    stt_docs = _DOCS + [_BASE + "speech-to-text.md"]
    tts_docs = _DOCS + [_BASE + "text-to-speech.md"]
    sts_docs = _DOCS + [_BASE + "speech-to-speech.md"]
    # The voice table is only in the HTML page (not the .md twin).
    voices_docs = [_BASE + "text-to-speech", _BASE + "voice.md"]
    stt_guidance = "Return every speech-to-text model id the API accepts (REST and streaming)."
    tts_guidance = "Return every text-to-speech model id the API accepts."
    sts_guidance = (
        "Return every realtime voice (speech-to-speech) model id the API accepts; '-latest' style ids are "
        "aliases (meta.alias_of) of the dated/versioned model they point to when the docs say so."
    )
    voices_guidance = (
        "Return the built-in voices with exact voice ids (never custom/cloned voices). compatible_models = "
        "the TTS and realtime models each voice works with. Gender/accent only when stated."
    )
