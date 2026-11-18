"""
Zoom AI Services — Scribe API speech-to-text.

Source: docs (developers.zoom.us/docs/ai-services/scribe*, especially Speech configuration, which lists the
recognition model ids) plus the Scribe API product page on zoom.com for per-hour pricing. No public model-list
endpoint. Zoom AI Services also has a TTS API without model selection and a cascaded Voice Agent API; neither is
synced here.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_BASE = "https://developers.zoom.us/docs/ai-services"


class ZoomSyncer(DocsOnlySyncer):
    provider_id = "zoom"
    stt_docs = [
        f"{_BASE}/scribe.md",
        f"{_BASE}/scribe/speech-configuration.md",
        f"{_BASE}/scribe/fast-mode.md",
        f"{_BASE}/scribe/batch-mode.md",
        f"{_BASE}/scribe/live-mode.md",
        "https://www.zoom.com/en/products/ai-services/scribe-api/",
    ]
    stt_guidance = (
        "Return every explicit recognition model id from the Speech configuration model table (skip id "
        "patterns with placeholders). Fast/Batch/Live are processing modes, not models: price per hour with "
        "the batch rate as base and other modes as variants; Pro models use the Pro rates."
    )
