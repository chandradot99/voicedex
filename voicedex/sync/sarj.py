"""
Sarj.ai (Saudi Arabia): Arabic-dialect STT and TTS.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class SarjSyncer(DocsOnlySyncer):
    provider_id = "sarj"
    stt_docs = [
        "https://platform-docs.sarj.ai/speech-to-text.md",
    ]
    stt_guidance = (
        "One record per callable STT model id (exact API string; if the API has no model parameter, one "
        "endpoint-level record with the endpoint in meta). Languages per model from the docs. Prices only "
        "from the vendor's own pages, in the published currency."
    )
    tts_docs = [
        "https://platform-docs.sarj.ai/text-to-speech.md",
    ]
    tts_guidance = (
        "One record per callable TTS model id (exact API string; if the API has no model parameter, one "
        "endpoint-level record with the endpoint in meta). Prices only from the vendor's own pages, in the "
        "published currency; credit plans → pricing.notes unless a per-unit rate is published."
    )
