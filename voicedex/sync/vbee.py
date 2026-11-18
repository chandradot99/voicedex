"""
Vbee (Hanoi): Vietnamese TTS API.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class VbeeSyncer(DocsOnlySyncer):
    provider_id = "vbee"
    tts_docs = [
        "https://api-docs.vbee.vn/vbee-api/text-to-speech/batch-api",
    ]
    tts_guidance = (
        "One record per TTS model/engine. Prices only from vbee.vn API pricing (VND or USD as published)."
    )
