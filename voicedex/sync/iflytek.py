"""
iFLYTEK — global open platform (global.xfyun.cn): Short Form ASR, Real-time ASR and Online TTS.

Source: docs (global.xfyun.cn/doc). There is no model-list API and the services expose no model id:
each WebSocket service (iat dictation, ist real-time transcription, tts synthesis) is one model here,
with the engine/language chosen by request parameters (`language`/`accent`/`domain`, `vcn` speaker).
Short Form ASR and Online TTS are priced per service call. The mainland platform (xfyun.cn) is a
separate, CNY-priced catalog and is not covered.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOC = "https://global.xfyun.cn/doc/"


class IflytekSyncer(DocsOnlySyncer):
    provider_id = "iflytek"
    stt_docs = [
        _DOC + "asr/voicedictation/API.html",
        _DOC + "rtasr/rtasr/API.html",
        _DOC + "platform/pricing.html",
        "https://global.xfyun.cn/products/real-time-asr",
    ]
    tts_docs = [_DOC + "tts/online_tts/API.html", _DOC + "platform/pricing.html"]
    voices_docs = [_DOC + "tts/online_tts/API.html"]
    stt_guidance = (
        "One model per speech-recognition WebSocket service (named by its endpoint path). Languages from the "
        "documented language/accent tables. Price only where a per-call or per-unit rate is published."
    )
    tts_guidance = "One model per text-to-speech service; per-call price from the pricing page."
    voices_guidance = "Return every documented speaker (vcn value) with its language and gender."
