"""
Volcengine Doubao Speech (豆包语音) — ByteDance's mainland-China speech platform (separate from BytePlus).

Source: docs (docs.volcengine.com, library 6561 / doubao-voice). Pages render client-side, but each has a
plain-markdown twin at docs.volcengine.com/docs/zh/doubao-voice/<slug>.md (index: .../doubao-voice/llms.txt),
which is what the seeds point at. Model ids are the `X-Api-Resource-Id` header values for ASR/TTS and the
`model` version string for the realtime speech-to-speech API. A voice-list OpenAPI (ListSpeakers) exists but
needs Volcengine AK/SK credentials, which require a CN real-name account — docs-only by decision (models,
prices and the voice list all come from the docs). Prices are CNY.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_MD = "https://docs.volcengine.com/docs/zh/doubao-voice/"
_BILLING = [_MD + "billing-instructions.md", _MD + "billing-overview.md"]


class VolcengineSyncer(DocsOnlySyncer):
    provider_id = "volcengine"
    stt_docs = [_MD + p + ".md" for p in (
        "model-list", "bidirectional-streaming-automatic-speech-recognition-websocket",
        "unidirectional-streaming-automatic-speech-recognition-websocket", "task-submission-http-1",
        "access-must-read-1", "access-must-read-1-1")] + _BILLING
    tts_docs = [_MD + p + ".md" for p in (
        "model-list", "unidirectional-streaming-text-to-speech-websocket", "websocket-unidirectional-streaming-v3",
        "audio-generation-http")] + _BILLING
    sts_docs = [_MD + p + ".md" for p in (
        "model-list", "end-to-end-real-time-voice-full-duplex-version",
        "end-to-endreal-time-speech-large-model-api-access-document", "simultaneous-interpretation")] + _BILLING
    voices_docs = [_MD + "tone-list-3.md"]
    stt_guidance = (
        "Return every speech-recognition X-Api-Resource-Id the docs list as callable (current and legacy "
        "versions still usable); one model per hour-billed resource id, concurrency-billed ids in meta. "
        "Prices in CNY per hour from the pay-as-you-go table; translate descriptions to English."
    )
    tts_guidance = (
        "Return every text-to-speech / voice-cloning / audio-generation resource or model id the API accepts, "
        "with CNY per-character (or per-minute) pay-as-you-go prices; translate descriptions to English."
    )
    sts_guidance = (
        "Return every end-to-end realtime speech-to-speech model version (the `model` value) and speech-to-speech "
        "interpretation service, with the CNY per-token prices (audio/text input and output as variants)."
    )
    voices_guidance = (
        "Return every preset voice_type in the online voice list with its name, language/accent, gender (from "
        "the id), and the model(s) its section says it works with. Skip cloned/custom voices."
    )
