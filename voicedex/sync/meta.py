"""
Meta (Meta Model API) — Muse Voice Transcribe speech-to-text.

Source: docs (dev.meta.ai). No public model-list endpoint for speech models.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class MetaSyncer(DocsOnlySyncer):
    provider_id = "meta"
    stt_docs = [
        "https://dev.meta.ai/docs/models",
        "https://dev.meta.ai/docs/speech-to-text",
        "https://dev.meta.ai/docs/pricing-rate-limits",
    ]
    stt_guidance = (
        "Return every speech-to-text model id callable on the Meta Model API (realtime and batch). "
        "Languages as BCP-47 — only the languages Meta lists as supported/validated (put trained-but-"
        "unvalidated counts in meta). Pricing only if Meta itself publishes it."
    )
