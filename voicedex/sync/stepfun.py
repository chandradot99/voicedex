"""
StepFun (international platform, platform.stepfun.ai) — StepAudio TTS, ASR and realtime.

Source: docs (English docs + USD pricing page). Voices are a static docs list.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOCS = [
    "https://platform.stepfun.ai/docs/en/guides/models/audio.md",
    "https://platform.stepfun.ai/docs/en/pricing/details",
]


class StepFunSyncer(DocsOnlySyncer):
    provider_id = "stepfun"
    stt_docs = _DOCS
    tts_docs = _DOCS
    sts_docs = _DOCS
    voices_docs = _DOCS
    stt_guidance = "Return every speech-to-text model id callable on the international API (api.stepfun.ai)."
    tts_guidance = "Return every text-to-speech model id callable on the international API (api.stepfun.ai)."
    sts_guidance = "Return every realtime speech-to-speech model id callable on the international API."
    voices_guidance = (
        "Return the official preset voices with exact voice ids and the TTS models each works with. "
        "Gender/language only when stated."
    )
