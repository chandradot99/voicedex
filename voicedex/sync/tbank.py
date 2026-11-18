"""
T-Bank (Tinkoff) VoiceKit: Russian STT/TTS API; T-one ASR also published as open weights (t-tech on Hugging Face).

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class TBankSyncer(DocsOnlySyncer):
    provider_id = "tbank"
    stt_docs = [
        "https://developer.tbank.ru/voicekit/api/speech-recognition",
        "https://developer.tbank.ru/voicekit/intro/tariff",
        "https://huggingface.co/t-tech/T-one",
    ]
    stt_guidance = (
        "One record per callable STT model id (exact API string; if the API has no model parameter, one "
        "endpoint-level record with the endpoint in meta). Languages per model from the docs. Prices only "
        "from the vendor's own pages, in the published currency. Set open_weights on a model only when the "
        "same model is published by t-tech on Hugging Face."
    )
    tts_docs = [
        "https://developer.tbank.ru/voicekit/api/synthesis/ttstutorial",
        "https://developer.tbank.ru/voicekit/intro/tariff",
    ]
    tts_guidance = (
        "One record per callable TTS model id (exact API string; if the API has no model parameter, one "
        "endpoint-level record with the endpoint in meta). Prices only from the vendor's own pages, in the "
        "published currency; credit plans → pricing.notes unless a per-unit rate is published."
    )
