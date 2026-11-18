"""
Voxist (Paris): French-first speech-to-text API (batch and realtime). Its TTS serves third-party open models
(Kyutai, OmniVoice), so only STT is catalogued.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class VoxistSyncer(DocsOnlySyncer):
    provider_id = "voxist"
    stt_docs = [
        "https://api-asr.voxist.com/docs",
        "https://github.com/Voxist/asr-websocket-samples",
    ]
    stt_guidance = (
        "One record per callable STT model id (exact API string) for batch and realtime. Languages per model from "
        "the docs. Prices only from Voxist's own pages, in EUR."
    )
