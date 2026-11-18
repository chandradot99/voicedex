"""
AISpeech 思必驰 (Suzhou) open platform: ASR and TTS sold as prepaid packs in CNY.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class AISpeechSyncer(DocsOnlySyncer):
    provider_id = "aispeech"
    stt_docs = [
        "https://cloud.aispeech.com/price",
    ]
    stt_guidance = (
        "One record per recognition product (realtime, file, short phrase …). Prices in CNY as published."
    )
    tts_docs = [
        "https://cloud.aispeech.com/price",
    ]
    tts_guidance = (
        "One record per synthesis tier (standard, premium …). Prices in CNY as published."
    )
