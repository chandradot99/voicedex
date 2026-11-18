"""
Chimege (Ulaanbaatar): Mongolian STT and TTS API.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class ChimegeSyncer(DocsOnlySyncer):
    provider_id = "chimege"
    stt_docs = [
        "https://docs.api.chimege.com/v1.2/en/",
    ]
    stt_guidance = (
        "One record per STT endpoint/model. Prices in MNT only from Chimege's own pages."
    )
    tts_docs = [
        "https://docs.api.chimege.com/v1.2/en/",
    ]
    tts_guidance = (
        "Same rules."
    )
