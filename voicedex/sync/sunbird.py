"""
Sunbird AI — speech-to-text (51 African languages) and Orpheus-based text-to-speech.

Source: docs (docs.sunbird.ai, llms.txt; OpenAPI at https://docs.sunbird.ai/api-reference/openapi.json).
`GET /tasks/voice/speakers` lists TTS speakers but needs a key — docs-only until a key is added; the speaker ids
per language are also published in the text-to-speech guide.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class SunbirdSyncer(DocsOnlySyncer):
    provider_id = "sunbird"
    stt_docs = [
        "https://docs.sunbird.ai/guides/speech-to-text.md",
        "https://docs.sunbird.ai/languages.md",
    ]
    tts_docs = [
        "https://docs.sunbird.ai/guides/text-to-speech.md",
        "https://docs.sunbird.ai/languages.md",
    ]
    voices_docs = ["https://docs.sunbird.ai/guides/text-to-speech.md"]
    stt_guidance = (
        "Return the model behind the unified transcription endpoint (no model parameter). Languages from the "
        "supported-languages table, converted from ISO 639-3 to the shortest BCP-47 code. No published price."
    )
    tts_guidance = (
        "Return the model behind the unified speech endpoint (the `model` value it reports). Languages are only "
        "those with at least one speaker id; training-mix-only languages go in meta."
    )
    voices_guidance = (
        "Return every speaker id in the per-language table (expand documented id ranges). The language is the "
        "row's language; gender is not documented."
    )
