"""
Voice.ai TTS API: dated TTS model snapshots with -latest aliases; USD credit plans.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class VoiceAISyncer(DocsOnlySyncer):
    provider_id = "voiceai"
    tts_docs = [
        "https://voice.ai/docs/api-reference/text-to-speech/generate-speech",
        "https://voice.ai/docs/guides/text-to-speech/quickstart",
        "https://voice.ai/pricing",
        "https://voice.ai/tts-lite",
    ]
    tts_guidance = (
        "One record per callable TTS model id (exact API string; if the API has no model parameter, one "
        "endpoint-level record with the endpoint in meta). Prices only from the vendor's own pages, in the "
        "published currency; credit plans → pricing.notes unless a per-unit rate is published. A cost figure for "
        "self-hosting an open model (e.g. '$X per 1M chars on your own CPU instance') is not a Voice.ai price: "
        "never put it in pricing; note it in meta.pricing_note."
    )
