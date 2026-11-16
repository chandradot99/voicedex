"""
BytePlus Seed Speech (ByteDance international) — Seed TTS / ASR.

Source: docs (docs.byteplus.com). Model ids are X-Api-Resource-Id header values. Seed Speech uses its own key, separate from ModelArk.
"""

from naaviq.sync.docs_only import DocsOnlySyncer

_BASE = "https://docs.byteplus.com/docs/en/byteplusvoice/"
# Docs pages render client-side; each has a plain-text twin at <page>.md (index: llms.txt).
_DOCS = [_BASE + p + ".md" for p in (
    "texttospeechv2", "streaming_tts", "speechtotextv2", "asrunidirect", "asraudiofilesubmittask",
    "asraudiofile-flash", "TTS_Billing", "asrbilling")]
_VOICE_DOCS = [_BASE + p + ".md" for p in ("tts-voice-list", "voicelist")]


class BytePlusSyncer(DocsOnlySyncer):
    provider_id = "byteplus"
    stt_docs = _DOCS
    tts_docs = _DOCS
    voices_docs = _VOICE_DOCS
    stt_guidance = "Return every speech recognition model/resource id the international API accepts."
    tts_guidance = (
        "Return every text-to-speech model/resource id the international API accepts; legacy 1.0 models only "
        "if still callable."
    )
    voices_guidance = "Return the official preset voices (exact voice_type ids), languages and gender when stated."
