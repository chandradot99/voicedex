"""
Zhipu AI / Z.ai — GLM-ASR speech recognition, GLM-TTS, GLM-Realtime and GLM-4-Voice.

Source: docs. Z.ai international (docs.z.ai, USD) documents the ASR model and its price; the mainland platform
(docs.bigmodel.cn, CNY) additionally documents GLM-TTS (system voices + voice cloning), the GLM-Realtime
audio/video call models and GLM-4-Voice. There is no public speech model-list endpoint, so this is docs-only.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class ZhipuSyncer(DocsOnlySyncer):
    provider_id = "zhipu"
    stt_docs = [
        "https://docs.z.ai/guides/audio/glm-asr-2512",
        "https://docs.z.ai/api-reference/audio/audio-transcriptions",
        "https://docs.z.ai/guides/overview/pricing",
        "https://docs.bigmodel.cn/cn/guide/start/pricing",
    ]
    tts_docs = [
        "https://docs.bigmodel.cn/api-reference/模型-api/文本转语音",
        "https://docs.bigmodel.cn/api-reference/模型-api/音色复刻",
        "https://docs.bigmodel.cn/cn/guide/start/pricing",
    ]
    sts_docs = [
        "https://docs.bigmodel.cn/cn/guide/models/sound-and-video/glm-realtime",
        "https://docs.bigmodel.cn/cn/guide/models/sound-and-video/glm-4-voice",
        "https://docs.bigmodel.cn/cn/guide/start/pricing",
    ]
    voices_docs = [
        "https://docs.bigmodel.cn/api-reference/模型-api/文本转语音",
        "https://docs.bigmodel.cn/cn/guide/models/sound-and-video/glm-realtime",
    ]
    stt_guidance = (
        "Return every speech recognition model id. Prefer Z.ai international USD pricing (per token as published); "
        "mention the bigmodel.cn CNY price in notes."
    )
    tts_guidance = (
        "Return every text-to-speech model id (voice cloning is a separate per-request priced step — a pricing "
        "variant, not a model). Prices are CNY only (bigmodel.cn): use currency CNY + price, never convert."
    )
    sts_guidance = (
        "Return every speech-to-speech / realtime voice model id (realtime call models and end-to-end voice chat "
        "models). Prices are CNY only: currency CNY + price; video-call rates as variants."
    )
    voices_guidance = (
        "Return the system voices from the TTS voice enum and the realtime voice table; compatible_models = the "
        "models whose docs list that voice. Gender only when the description states it."
    )
