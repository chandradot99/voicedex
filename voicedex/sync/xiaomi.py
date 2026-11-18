"""
Xiaomi MiMo API Open Platform — MiMo ASR and TTS (built-in voices, voice design, voice cloning).

Source: docs (mimo.mi.com/docs/en-US; raw Markdown under mimo.mi.com/static/docs, indexed by mimo.mi.com/llms.txt).
GET /v1/models exists on api.xiaomimimo.com but needs an API key and returns ids only — docs-only until a key
is added. Overseas prices are USD, mainland prices CNY, on the pay-as-you-go page.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOCS = "https://mimo.mi.com/static/docs"


class XiaomiSyncer(DocsOnlySyncer):
    provider_id = "xiaomi"
    stt_docs = [
        f"{_DOCS}/quick-start/summary/model.md",
        f"{_DOCS}/quick-start/usage-guide/audio/Speech-Recognition.md",
        f"{_DOCS}/price/pay-as-you-go.md",
    ]
    tts_docs = [
        f"{_DOCS}/quick-start/summary/model.md",
        f"{_DOCS}/quick-start/usage-guide/audio/speech-synthesis-v2.5.md",
        f"{_DOCS}/api/audio/tts-post.md",
        f"{_DOCS}/price/pay-as-you-go.md",
    ]
    voices_docs = [
        f"{_DOCS}/quick-start/usage-guide/audio/speech-synthesis-v2.5.md",
        f"{_DOCS}/api/audio/tts-post.md",
    ]
    stt_guidance = (
        "Return every speech recognition model id on the models page. Overseas (USD) price per hour of input audio; "
        "CNY price in notes. Set open_weights only if the same model is published as weights by Xiaomi."
    )
    tts_guidance = (
        "Return every TTS model id (base, voice-design and voice-clone variants). Streaming = true only where "
        "low-latency streaming is available (not compatibility mode). If TTS is free for a limited time, omit "
        "pricing and say so in meta."
    )
    voices_guidance = (
        "Return every built-in voice (exact voice id, including the default alias) with language and gender from "
        "the table; compatible_models = the models that accept built-in voices."
    )
