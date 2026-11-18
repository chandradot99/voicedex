"""
Reson8 (Resonate Labs B.V., NL): prerecorded and realtime STT.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class Reson8Syncer(DocsOnlySyncer):
    provider_id = "reson8"
    stt_docs = [
        "https://docs.reson8.dev/llms-full.txt",
        "https://www.reson8.dev/pricing",
    ]
    stt_guidance = (
        "One record per callable STT model id. Prices only from the vendor's own pages (currency as "
        "published; EUR → currency + price)."
    )
