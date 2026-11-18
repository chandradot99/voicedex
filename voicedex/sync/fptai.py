"""
FPT.AI (FPT Smart Cloud, Vietnam) — Vietnamese text-to-speech (v5) and speech-to-text.

Source: docs (docs.fpt.ai speech API reference + pricing pages). The REST endpoints
(api.fpt.ai/hmi/tts/v5, api.fpt.ai/hmi/asr/general) need an `api_key` from console.fpt.ai and there is no
model- or voice-list endpoint, so models and the documented stock voices come from the docs.
Pricing is published only as VND prepaid packs (no per-unit rate), so packs go in model meta, not pricing.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class FptAISyncer(DocsOnlySyncer):
    provider_id = "fptai"
    tts_docs = [
        "https://docs.fpt.ai/docs/en/speech/api/text-to-speech/",
        "https://docs.fpt.ai/docs/en/speech/documentation/text-to-speech/",
        "https://docs.fpt.ai/docs/en/speech/documentation/tts-pricing/",
    ]
    stt_docs = [
        "https://docs.fpt.ai/docs/en/speech/api/speech-to-text/",
        "https://docs.fpt.ai/docs/en/speech/documentation/speech-to-text/",
        "https://docs.fpt.ai/docs/en/speech/documentation/stt-pricing/",
    ]
    voices_docs = ["https://docs.fpt.ai/docs/en/speech/api/text-to-speech/"]
    tts_guidance = (
        "One model per documented TTS API version (the version segment of the endpoint path). Pricing is sold as "
        "VND packs of characters — record packs and the free tier in meta, not as a per-unit price."
    )
    stt_guidance = (
        "One model per documented speech-to-text endpoint. Pricing is sold as VND minute packs — record packs and "
        "the trial allowance in meta, not as a per-unit price."
    )
    voices_guidance = (
        "Every voice id in the TTS API reference's voice table, with gender and the regional accent it lists."
    )
