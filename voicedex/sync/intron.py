"""
Intron — Sahara speech recognition and text-to-speech for African accents and languages (Intron Voice API).

Source: docs (docs.voice.intron.io). The API has no model parameter: transcription is selected by language
code, synthesis by language + accent + gender, so each section is one engine record. No model, voice or
price list endpoint; usage is billed against a credit balance on voice.intron.io and per-unit rates are
not published.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOCS = "https://docs.voice.intron.io/docs/"


class IntronSyncer(DocsOnlySyncer):
    provider_id = "intron"
    stt_docs = [
        _DOCS + "stt/supported-languages",
        _DOCS + "stt/file-upload-sync",
        _DOCS + "stt/file-upload",
        _DOCS + "stt/streaming",
    ]
    tts_docs = [
        _DOCS + "tts/supported-languages-and-accents",
        _DOCS + "tts/tts-generate",
        _DOCS + "tts/tts-queue",
        _DOCS + "tts/tts-streaming",
    ]
    stt_guidance = (
        "Transcription has no model parameter: return one engine record with every language code in the "
        "supported-languages table (code-switched codes in meta), the documented file formats and endpoints."
    )
    tts_guidance = (
        "Synthesis has no model or voice id (language + accent + gender): return one engine record with the "
        "documented languages, output formats and character limits; accents in meta. No voice records."
    )
