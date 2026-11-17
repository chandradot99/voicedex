"""
Async (async.com, formerly async.ai) — TTS + ASR models.

Source: docs (docs.async.com). Voices: the stock library is only listable via
POST https://api.async.com/voices (X-Api-Key; paginated, filters incl. my_voice) — not in the
public docs, so voices are not synced until an ASYNC_API_KEY is available (backlog).
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOCS = [
    "https://docs.async.com/llms.txt",
    "https://docs.async.com/models-2161359m0.md",
    "https://docs.async.com/billing-pricing-2243956m0.md",
]


class AsyncSyncer(DocsOnlySyncer):
    provider_id = "async"
    stt_docs = _DOCS
    tts_docs = _DOCS
    stt_guidance = "Return every speech-to-text model id the API accepts. is_default = the recommended model."
    tts_guidance = (
        "Return every text-to-speech model id the API accepts. is_default = the model the docs recommend for "
        "real-time use. Per-model languages, interfaces (http/websocket), USD pricing from the billing page."
    )
