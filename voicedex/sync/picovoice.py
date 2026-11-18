"""
Picovoice — on-device speech engines: Leopard (batch STT), Cheetah (streaming STT), Orca (streaming TTS).

Source: docs (picovoice.ai/docs/<engine>/ and the engine READMEs / lib/common model files on
github.com/Picovoice). Engines run locally via SDKs (no hosted API, so interfaces stay empty); an AccessKey
validates the licence. Pricing is licence/plan based, not per unit. Wake-word, intent and diarization-only
engines are not STT/TTS models and are out of scope. Docs-only.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class PicovoiceSyncer(DocsOnlySyncer):
    provider_id = "picovoice"
    stt_docs = [
        "https://picovoice.ai/docs/leopard/",
        "https://picovoice.ai/docs/cheetah/",
        "https://github.com/Picovoice/leopard",
        "https://github.com/Picovoice/cheetah",
    ]
    tts_docs = [
        "https://picovoice.ai/docs/orca/",
        "https://github.com/Picovoice/orca",
    ]
    voices_docs = ["https://github.com/Picovoice/orca/tree/main/lib/common"]
    stt_guidance = (
        "One model per on-device speech-to-text engine (lowercase engine name as model_id); the batch engine "
        "has streaming false. Languages from the per-language model files / Language Support section. "
        "interfaces = []; meta.deployment = 'on_device', meta.version = latest release. No per-unit pricing."
    )
    tts_guidance = (
        "One model per on-device text-to-speech engine (lowercase engine name as model_id). Languages from the "
        "Language Support section. interfaces = []; meta.deployment = 'on_device'. No per-unit pricing."
    )
    voices_guidance = (
        "One voice per stock voice model file (.pv) in lib/common; voice_id = file name without extension; "
        "language and gender from the file name; compatible_models = ['*']."
    )
