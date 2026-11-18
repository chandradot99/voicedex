"""
Lelapa AI — Vulavula speech-to-text for South African and other African languages.

Source: docs (docs.lelapa.ai, served as Markdown by appending `.md`). The API has no model parameter or list
endpoint: sync transcription and the Live API (early beta, enterprise-only WebSocket) are each one model.
Plans are priced per API call (monthly bundles), not per unit.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class LelapaSyncer(DocsOnlySyncer):
    provider_id = "lelapa"
    stt_docs = [
        "https://docs.lelapa.ai/transcribe/sync.md",
        "https://docs.lelapa.ai/live/realtime.md",
        "https://docs.lelapa.ai/overview/language-support.md",
        "https://docs.lelapa.ai/overview/plans.md",
    ]
    stt_guidance = (
        "Return one model per transcription product (sync REST, live WebSocket). Languages from each product's "
        "supported language codes; per-language Beta status goes in meta. Plans are monthly call bundles: "
        "record them in meta unless an explicit per-call price is published."
    )
