"""
Reverie Language Technologies — RevUp speech APIs (streaming / file / batch speech-to-text and text-to-speech).

Source: docs (docs.reverieinc.com, Mintlify; llms.txt index). Reverie has no model-list endpoint: the product is
selected with the ``REV-APPNAME`` header (or ``appname`` on the WebSocket), so each documented speech app name is
recorded as one model, and TTS speaker codes (``speaker`` header) are the voices. The OpenAPI spec at
/api-reference/openapi.json covers only text endpoints. Paid pricing is behind a contact form on revup.reverieinc.com
(only the free tier is published), so no prices are recorded.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOCS = "https://docs.reverieinc.com"


class ReverieSyncer(DocsOnlySyncer):
    provider_id = "reverie"
    stt_docs = [
        f"{_DOCS}/usage-guides/speech-to-text/supported-languages",
        f"{_DOCS}/usage-guides/speech-to-text/supported-audio-formats",
        f"{_DOCS}/usage-guides/speech-to-text/supported-domains",
        f"{_DOCS}/api-reference/speech-to-text-streaming",
        f"{_DOCS}/api-reference/speech-to-text-file",
        f"{_DOCS}/api-reference/speech-to-text-batch",
        f"{_DOCS}/analytics",
    ]
    tts_docs = [
        f"{_DOCS}/api-reference/text-to-speech",
        f"{_DOCS}/usage-guides/text-to-speech/key-features",
        f"{_DOCS}/usage-guides/text-to-speech/supported-speakers",
        f"{_DOCS}/usage-guides/text-to-speech/supported-audio-formats",
        f"{_DOCS}/usage-guides/text-to-speech/supported-sampling-rates",
    ]
    voices_docs = [f"{_DOCS}/usage-guides/text-to-speech/supported-speakers"]
    stt_guidance = (
        "One model per documented speech-to-text REV-APPNAME value (the exact header/appname string is the "
        "model_id). Languages from the shared supported-languages page; code-mixed codes (xx_en) go in meta, "
        "not languages. Streaming only for the WebSocket app. Capabilities only where the API reference "
        "documents them (e.g. a punctuate flag, word start/end times in the response). Prices only if a "
        "per-unit number is published (the free tier is not a price)."
    )
    tts_guidance = (
        "One model per documented text-to-speech REV-APPNAME value. Languages = those with speakers listed. "
        "Output formats and sample rates from the supported-formats/sampling-rates pages; SSML and "
        "speed/pitch controls only as documented. No prices unless a per-unit number is published."
    )
    voices_guidance = (
        "Every speaker code in the speakers table is a voice: voice_id = the exact code, gender from the "
        "Male/Female column, language from the row (Indian English = en-IN). compatible_models = ['*']."
    )
