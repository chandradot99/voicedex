"""
Baidu AI Cloud speech technology (语音技术): ASR, TTS, voice cloning and a realtime speech LLM. Prices in CNY. Fetch with a browser User-Agent (cloud.baidu.com resets non-browser clients).

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class BaiduSyncer(DocsOnlySyncer):
    provider_id = "baidu"
    stt_docs = [
        "https://cloud.baidu.com/doc/SPEECH/s/Ck5ymfh10",
        "https://cloud.baidu.com/doc/SPEECH/s/Tldjm0i4c",
        "https://cloud.baidu.com/doc/SPEECH/s/Cmwkauvx8",
        "https://cloud.baidu.com/doc/SPEECH/s/xmw03avls",
        "https://cloud.baidu.com/doc/SPEECH/s/Wl9mh4doe",
    ]
    stt_guidance = (
        "One record per callable recognition product/model (dev_pid or model value where documented). Prices "
        "in CNY as published (currency + price), per call/hour; tier discounts as variants."
    )
    tts_docs = [
        "https://cloud.baidu.com/doc/SPEECH/s/Ck5ymfh10",
        "https://cloud.baidu.com/doc/SPEECH/s/Ql9misjot",
        "https://cloud.baidu.com/doc/SPEECH/s/vm9sbp4z9",
        "https://cloud.baidu.com/doc/SPEECH/s/Wmtlcgi7c",
    ]
    tts_guidance = (
        "One record per TTS tier/product a developer selects (basic, premium, LLM voices, long- "
        "text/streaming). Prices in CNY as published; voice cloning price in meta or a variant."
    )
    sts_docs = [
        "https://cloud.baidu.com/doc/SPEECH/s/nmcytnwei",
        "https://cloud.baidu.com/doc/SPEECH/s/Tmq8y6vdh",
    ]
    sts_guidance = (
        "One record per documented realtime speech-model id. Prices in CNY as published."
    )
