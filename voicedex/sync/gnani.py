"""
Gnani.ai — Vachana speech APIs: Prisma speech-to-text, Timbre text-to-speech and voice-cloned TTS.

Source: docs (docs.gnani.ai, Mintlify; llms.txt + per-page .md). No model- or voice-list endpoint is
documented, and pricing is not published (sales-led), so this provider is docs-only with no prices.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOCS = "https://docs.gnani.ai/api/"


class GnaniSyncer(DocsOnlySyncer):
    provider_id = "gnani"
    stt_docs = [
        _DOCS + "STT/models/overview.md",
        _DOCS + "STT/limits.md",
        _DOCS + "STT/stt-websocket.md",
        _DOCS + "STTBatch/Introduction.md",
    ]
    tts_docs = [
        _DOCS + "TTS/tts-inference.md",
        _DOCS + "TTS/available-voices.md",
        _DOCS + "VC/vc-inference.md",
    ]
    voices_docs = [_DOCS + "TTS/available-voices.md"]
    stt_guidance = (
        "Return every speech-to-text model id listed on the Models overview (follow each model's own page for "
        "languages, formats and limits). The default is the model the API uses when `model` is omitted."
    )
    tts_guidance = (
        "Return every text-to-speech model id accepted by the TTS and voice-cloning endpoints. No price unless "
        "Gnani publishes one."
    )
    voices_guidance = (
        "Return every voice in each model's voice catalog; voices are model-specific, so set compatible_models "
        "to that model only. Use the exact voice name the API accepts."
    )
