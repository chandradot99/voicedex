"""
Daglo by ActionPower (Seoul): Korean-first speech-to-text API.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class DagloSyncer(DocsOnlySyncer):
    provider_id = "daglo"
    stt_docs = [
        "https://developers.daglo.ai/guide/en/STT-Async.html",
        "https://apis.daglo.ai/en/docs",
        "https://developers.daglo.ai/pricing",
    ]
    stt_guidance = (
        "One record per callable STT model id (exact API string; if the API has no model parameter, one "
        "endpoint-level record with the endpoint in meta). Languages per model from the docs. Prices only "
        "from the vendor's own pages, in the published currency."
    )
