"""
Voicegain — speech-to-text acoustic models (Omega/Kappa families, hosted Whisper) on the Voicegain cloud.

Source: docs. Model names come from the acousticModelRealTime / acousticModelNonRealTime parameter docs in
Voicegain's OpenAPI-generated python-sdk (github.com/voicegain/python-sdk), model positioning from
voicegain.ai/developers, price from voicegain.ai/pricing. No public model-list endpoint; docs-only.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class VoicegainSyncer(DocsOnlySyncer):
    provider_id = "voicegain"
    stt_docs = [
        "https://github.com/voicegain/python-sdk/blob/master/voicegain_speech/models/asr_settings_transcription_async.py",
        "https://www.voicegain.ai/developers",
        "https://www.voicegain.ai/pricing",
    ]
    stt_guidance = (
        "Return every cloud acoustic model name accepted by acousticModelRealTime / acousticModelNonRealTime "
        "(exact strings). Real-time models stream; offline-only models are batch (streaming false). Edge-only "
        "versioned model names are not catalog models. Languages only where Voicegain states them per model. "
        "Price is the published per-second cloud STT rate (note the per-request minimum)."
    )
