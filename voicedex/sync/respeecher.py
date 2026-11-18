"""
Respeecher — two APIs: the Space API (realtime text-to-speech, one model per primary language) and the Voice
Marketplace API (speech-to-speech voice conversion plus text-to-speech, order based).

Source: docs (https://space.respeecher.com/docs/llms.txt; Markdown pages via ".md"; OpenAPI at /docs/openapi.json).
Space TTS models are the per-language base URLs (api.respeecher.com/v1/public/tts/<model>), served over Bytes
(HTTP), SSE and WebSocket. The Marketplace API (gateway.respeecher.com) has no model parameter: you upload or
synthesise a recording, then order conversions to a target voice (with an accent for STS, a narration style for
TTS), poll and download. Its voice conversion is recorded as an `sts` model (audio in, converted audio out; not
streaming) and its TTS as a separate non-streaming `tts` model. Prices: Space TTS from respeecher.com/real-time-tts-api,
Marketplace credits from respeecher.com/marketplace/pricing. Both voice lists (Space GET /voices, Marketplace
GET /api/v2/voices) need an API key — docs-only, no voices, until a key is added.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOCS = "https://space.respeecher.com/docs/"


class RespeecherSyncer(DocsOnlySyncer):
    provider_id = "respeecher"
    tts_docs = [
        _DOCS + "llms.txt",
        _DOCS + "choosing-an-api.md",
        _DOCS + "space/models-and-languages.md",
        _DOCS + "space/limits.md",
        _DOCS + "space/api/tts/bytes.md",
        _DOCS + "space/api/tts/sse.md",
        _DOCS + "marketplace/api-overview.md",
        "https://www.respeecher.com/real-time-tts-api",
        "https://www.respeecher.com/marketplace/pricing",
    ]
    sts_docs = [
        _DOCS + "choosing-an-api.md",
        _DOCS + "marketplace/api-overview.md",
        "https://www.respeecher.com/marketplace/pricing",
    ]
    tts_guidance = (
        "Return one model per Space API base-URL model in the Models & Languages table (model_id = the path "
        "segment), with its primary language, output encodings, sample rate and per-request limit; mark the "
        "model the docs call the SDK default as default. Also return one non-streaming model for Marketplace "
        "API text-to-speech. Prices only as published per character by Respeecher."
    )
    sts_guidance = (
        "Return one model for Marketplace API speech-to-speech voice conversion (order-based, not streaming), "
        "with accepted input formats and the published per-minute credit price."
    )
