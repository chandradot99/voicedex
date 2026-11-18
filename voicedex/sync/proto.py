"""
Proto (Waterloo, CA; offices in the Philippines and Rwanda) Voice API: STT and TTS for under-served languages, request-credit pricing.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class ProtoSyncer(DocsOnlySyncer):
    provider_id = "proto"
    stt_docs = [
        "https://proto.cx/voice-api",
        "https://documentation.proto.cx/docs/developers/apis/voice-api",
    ]
    stt_guidance = (
        "One record per STT model/endpoint. Languages per model from the docs, not the marketing headline "
        "count. Credit pricing: publish the USD-per-request credit rate as unit=request with tiers as "
        "variants."
    )
    tts_docs = [
        "https://proto.cx/voice-api",
        "https://documentation.proto.cx/docs/developers/apis/voice-api",
    ]
    tts_guidance = (
        "One record per TTS model/endpoint; same pricing rule."
    )
