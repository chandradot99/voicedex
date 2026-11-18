"""
Humelo PROSODY (Seoul): Korean TTS API.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class HumeloSyncer(DocsOnlySyncer):
    provider_id = "humelo"
    tts_docs = [
        "https://console.humelo.com/docs",
        "https://console.humelo.com/llms-full.txt",
    ]
    tts_guidance = (
        "One record per TTS model the API exposes. KRW subscription prices go in pricing.notes; set a per- "
        "unit price only if one is published."
    )
