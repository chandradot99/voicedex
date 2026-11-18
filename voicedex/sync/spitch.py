"""
Spitch — speech-to-text and text-to-speech for Nigerian and other African languages.

Source: docs (spitch.app/docs, a client-rendered app; the machine-readable API spec is at
https://api.spitch.app/openapi.json and the Python SDK at github.com/spi-tch/spitch-python). The API takes no
model parameter for TTS (and the STT `model` parameter is deprecated), so each modality is one endpoint-level
model. `GET /v1/voices` exists but needs a key — docs-only until a key is added; the system voices are listed on
the voices concepts page.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class SpitchSyncer(DocsOnlySyncer):
    provider_id = "spitch"
    stt_docs = [
        "https://spitch.app/docs/features/transcription",
        "https://spitch.app/docs/api-reference/speech/speech-to-text",
        "https://spitch.app/pricing",
    ]
    tts_docs = [
        "https://spitch.app/docs/features/speech",
        "https://spitch.app/docs/api-reference/speech/text-to-speech",
        "https://spitch.app/pricing",
    ]
    voices_docs = ["https://spitch.app/docs/concepts/voices"]
    stt_guidance = (
        "The transcription endpoint has no current model selector; describe it as one endpoint-level model. "
        "Languages are the ISO 639 codes the docs name. Pricing per second of input audio as published."
    )
    tts_guidance = (
        "The speech endpoint has no model parameter; describe it as one endpoint-level model. Languages are "
        "those the docs say voices cover. Pricing per second of generated audio as published."
    )
    voices_guidance = (
        "Return every system voice; the voice id is the lowercase card name. Gender from the card. Every voice "
        "speaks every supported language, so list the TTS languages and keep the design language in meta."
    )
