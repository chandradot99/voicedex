"""
Alibaba Cloud Model Studio (international) — Qwen speech: ASR, TTS, realtime omni/speech models.

Source: docs (alibabacloud.com/help/en/model-studio). An API exists
(GET https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/api/v1/models, with prices and
retirement dates), but international sign-up isn't available to us — see backlog.
Only models offered in the international deployment (Singapore and other non-mainland regions) count;
China-mainland-only models (e.g. CosyVoice in Beijing) are excluded.
"""

from naaviq.sync.docs_only import DocsOnlySyncer

_B = "https://www.alibabacloud.com/help/en/model-studio/"
_COMMON = [_B + "models", _B + "model-pricing", _B + "model-depreciation.md"]


class AlibabaSyncer(DocsOnlySyncer):
    provider_id = "alibaba"
    stt_docs = _COMMON + [_B + "asr-model", _B + "qwen-asr-api-reference"]
    tts_docs = _COMMON + [_B + "tts-model", _B + "non-realtime-tts-user-guide"]
    sts_docs = _COMMON + [_B + "s2s-model", _B + "realtime", _B + "qwen-audio-realtime-user-guides"]
    voices_docs = [_B + "qwen-audio-tts-voice-list", _B + "qwen-tts-voice-list", _B + "cosyvoice-voice-list"]
    _INTL = (" Only models available in the international deployment (not China-mainland-only). Include dated "
             "snapshots only if the docs list them as callable ids; moving names (e.g. without a date) that the "
             "docs say point to a snapshot get meta.alias_of. Retirement dates → eol_date only when published "
             "and in the future. USD prices from the international pricing table.")
    stt_guidance = "Return every speech recognition (ASR) model id." + _INTL
    tts_guidance = "Return every text-to-speech model id." + _INTL
    sts_guidance = "Return every realtime speech-in/speech-out model id (realtime omni and speech models)." + _INTL
    voices_guidance = (
        "Return the system voices for the international TTS models with exact voice ids; compatible_models = the "
        "model ids each voice supports; languages/dialects and gender only when stated. Never cloned/custom voices."
    )
