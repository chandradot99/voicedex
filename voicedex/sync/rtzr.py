"""
ReturnZero (RTZR) — RTZR STT OpenAPI (formerly VITO), Korean-focused batch and streaming speech-to-text.

Source: docs (developers.rtzr.ai/docs/en). Models are the `model_name` values accepted by the Batch STT
(POST /v1/transcribe) and Streaming STT (gRPC / WebSocket) APIs; there is no model-list endpoint.
Pricing is KRW per hour, tiered by monthly usage, from the developer docs pricing page.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOCS = "https://developers.rtzr.ai/docs/en/"


class RtzrSyncer(DocsOnlySyncer):
    provider_id = "rtzr"
    stt_docs = [
        _DOCS + "stt-file/",
        _DOCS + "stt-file/model/",
        _DOCS + "stt-file/language/",
        _DOCS + "stt-streaming/",
        _DOCS + "pricing/",
    ]
    stt_guidance = (
        "Return every model_name accepted by Batch STT or Streaming STT, one model each; mark streaming only "
        "for names the streaming DecoderConfig accepts and batch for names the batch API accepts. Languages "
        "per the model and language pages. Price: KRW per hour (currency + price), first tier as the main "
        "price and higher-volume tiers as variants."
    )
