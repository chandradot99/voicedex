"""
Unisound 云知声 (Beijing) open platform: ASR and TTS.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class UnisoundSyncer(DocsOnlySyncer):
    provider_id = "unisound"
    stt_docs = [
        "https://ai.unisound.com",
    ]
    stt_guidance = (
        "One record per recognition product. Prices only if published (CNY)."
    )
    tts_docs = [
        "https://ai.unisound.com",
    ]
    tts_guidance = (
        "One record per synthesis product/tier. Prices only if published (CNY)."
    )
