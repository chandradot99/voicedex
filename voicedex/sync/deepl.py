"""
DeepL (Cologne) Voice API — real-time speech transcription + translation (GA 2026-02-02, API Pro).

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class DeepLSyncer(DocsOnlySyncer):
    provider_id = "deepl"
    stt_docs = [
        "https://developers.deepl.com/docs/api-reference/voice",
        "https://developers.deepl.com/docs/voice/supported-voice-languages.md",
        "https://www.deepl.com/en/pro?tab=api",
    ]
    stt_guidance = (
        "One record per callable speech model/endpoint the Voice API documents (if no model parameter exists, "
        "one endpoint-level model named after the product). Source languages = transcription languages; put "
        "translation target languages in meta. capabilities: translation where the docs say the API "
        "translates speech. Only published per-unit prices."
    )
