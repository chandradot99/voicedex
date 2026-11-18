"""
SK Telecom open API portal: A.X TTS.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class SKTSyncer(DocsOnlySyncer):
    provider_id = "skt"
    tts_docs = [
        "https://openapi.sk.com/products/detail?svcSeq=67",
        "https://ax-tts-skopenapi.readme.io/reference/tts-model-list-1",
        "https://openapi.sk.com/products/calc?svcSeq=67",
    ]
    tts_guidance = (
        "One record per callable TTS model id (exact API string; if the API has no model parameter, one "
        "endpoint-level record with the endpoint in meta). Prices only from the vendor's own pages, in the "
        "published currency; credit plans → pricing.notes unless a per-unit rate is published."
    )
