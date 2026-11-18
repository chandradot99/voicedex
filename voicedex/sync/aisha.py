"""
Aisha AI (by VoiceLab, Tashkent) — Uzbek-first text-to-speech and speech-to-text.

Source: docs (https://aisha.group/llms-api.txt and the human API reference at aisha.group/en/api-documentation).
No list endpoint for models or voices. Prices are published in UZS on aisha.group/en/pricing.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class AishaSyncer(DocsOnlySyncer):
    provider_id = "aisha"
    stt_docs = [
        "https://aisha.group/en/api-documentation/speech-to-text",
        "https://aisha.group/en/pricing",
    ]
    tts_docs = [
        "https://aisha.group/en/api-documentation/text-to-speech",
        "https://aisha.group/en/pricing",
    ]
    stt_guidance = (
        "The STT API has no model parameter; describe it as one endpoint-level model. Languages from the "
        "documented `language` values. Price in UZS per minute as published (currency + price)."
    )
    tts_guidance = (
        "Return each value accepted by the TTS `model` field. Moods and realtime speaker ids go in meta. Price in "
        "UZS per character as published (currency + price)."
    )
