"""
Krutrim (Ola, Bengaluru) AI Studio: Indic speech models billed per minute/hour of audio in INR.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class KrutrimSyncer(DocsOnlySyncer):
    provider_id = "krutrim"
    stt_docs = [
        "https://docs.cloud.olakrutrim.com/api-references/bhashik-speech-api",
    ]
    stt_guidance = (
        "Only speech models Krutrim built itself (state hosted third-party models are excluded). Prices in "
        "INR only from a Krutrim page."
    )
    tts_docs = [
        "https://docs.cloud.olakrutrim.com/api-references/bhashik-speech-api",
    ]
    tts_guidance = (
        "Same rules as STT."
    )
