"""
Unisound 云知声 (Beijing) open platform: ASR and TTS.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class UnisoundSyncer(DocsOnlySyncer):
    provider_id = "unisound"
    stt_docs = [
        "https://maas.unisound.com/docs/api/overview",
        "https://maas.unisound.com/docs/price/overview",
    ]
    stt_guidance = (
        "One record per recognition product. Prices only if published (CNY)."
    )
    tts_docs = [
        "https://maas.unisound.com/docs/api/overview",
        "https://maas.unisound.com/docs/price/overview",
    ]
    tts_guidance = (
        "One record per synthesis product/tier. Prices only if published (CNY)."
    )
