"""
Tencent Cloud — Automatic Speech Recognition (ASR) and Text to Speech (TTS), international site.

Source: docs (tencentcloud.com, products 1118 ASR / 1154 TTS). Neither service has a model-list API.
STT "models" are the ASR engine types passed as `engine_model_type` / `EngineModelType` (e.g. 8k vs 16k,
per-language and "large model" engines); the real-time WebSocket API and the recording-file API
(CreateRecTask) share these ids. TTS has no model id: the international docs group VoiceType ids into
Standard and Premium voice tiers that are priced differently, so each tier is one TTS model and every
VoiceType is a voice of its tier. The mainland site (cloud.tencent.com, products 1093/1073) has a larger,
separately priced CNY catalog; this syncer follows the international site.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_INTL = "https://www.tencentcloud.com/document/"


class TencentSyncer(DocsOnlySyncer):
    provider_id = "tencent"
    stt_docs = [
        _INTL + "api/1118/53937",       # real-time ASR (WebSocket) — engine list
        _INTL + "api/1118/66925",       # CreateRecTask (recording file recognition)
        _INTL + "product/1118/43352",   # ASR billing
    ]
    tts_docs = [
        _INTL + "api/1154/48916",       # TextToVoice — VoiceType tiers
        _INTL + "product/1154/47874",   # TTS billing
    ]
    voices_docs = [_INTL + "api/1154/48916"]
    stt_guidance = (
        "Return every ASR engine type id (engine_model_type / EngineModelType) the international API accepts, "
        "one model per engine. Languages from the engine description. Price per hour from the billing page: "
        "large-model engines use the large-model price; real-time as the main price, recording-file as a variant."
    )
    tts_guidance = (
        "Tencent TTS has no model id; return one model per documented voice tier (as named in the VoiceType "
        "table), with that tier's per-character price."
    )
    voices_guidance = (
        "Return every VoiceType id in the international TextToVoice docs with its name, language and tier "
        "(compatible_models = the tier model). Gender only when stated."
    )
