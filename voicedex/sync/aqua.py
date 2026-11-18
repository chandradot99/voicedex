"""
Aqua Voice Avalon API: OpenAI-compatible speech-to-text.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class AquaSyncer(DocsOnlySyncer):
    provider_id = "aqua"
    stt_docs = [
        "https://aquavoice.com/llms.txt",
        "https://aquavoice.com/docs/api/openapi.yaml",
        "https://aquavoice.com/api",
    ]
    stt_guidance = (
        "One record per callable model id. Prices only from Aqua's own pages."
    )
