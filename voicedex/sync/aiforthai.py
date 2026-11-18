"""
AI for Thai (NECTEC, Thailand): Partii ASR and Vaja TTS; registration requires a Thai ID.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class AIForThaiSyncer(DocsOnlySyncer):
    provider_id = "aiforthai"
    stt_docs = [
        "https://aiforthai.in.th/en/services/conversation/text-to-speech",
        "https://github.com/AIforThai/aiforthai",
    ]
    stt_guidance = (
        "One record per callable STT model id (exact API string; if the API has no model parameter, one "
        "endpoint-level record with the endpoint in meta). Languages per model from the docs. Prices only "
        "from the vendor's own pages, in the published currency."
    )
    tts_docs = [
        "https://aiforthai.in.th/en/services/conversation/text-to-speech",
        "https://github.com/AIforThai/aiforthai",
        "https://vaja.openservice.in.th/",
    ]
    tts_guidance = (
        "One record per callable TTS model id (exact API string; if the API has no model parameter, one "
        "endpoint-level record with the endpoint in meta). Prices only from the vendor's own pages, in the "
        "published currency; credit plans → pricing.notes unless a per-unit rate is published."
    )
