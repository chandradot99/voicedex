"""
SESTEK (Knovvu) — Knovvu SR speech recognition models and Knovvu TTS voices (Standard, Flash and Premium tiers).

Source: docs (docs.sestek.com; index at https://docs.sestek.com/llms.txt). SR model names come from the documented,
unauthenticated GET <region>/v1/speech/dictation/models endpoint on each cloud region (see sr-cloud-api-region-urls;
a future API syncer could call it directly). Whisper- and Dolphin-family models SESTEK hosts but did not build are
excluded. TTS has no model parameter (the tier is implied by the voice name); voices come from the supported-voices
table — GET /v1/speech/synthesis/voices needs a token. No published prices (credit-based, sales-led).
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOCS = "https://docs.sestek.com/docs/"


class SestekSyncer(DocsOnlySyncer):
    provider_id = "sestek"
    stt_docs = [
        _DOCS + "sr-supported-languages-and-models.md",
        _DOCS + "sr-language-models.md",
        _DOCS + "sr-cloud-api-region-urls.md",
        _DOCS + "sr-transcription.md",
        _DOCS + "sr-transcribe-a-file.md",
        _DOCS + "sr-transcribe-in-real-time.md",
        _DOCS + "sr-features.md",
    ]
    tts_docs = [
        _DOCS + "tts-supported-languages-and-voices.md",
        _DOCS + "tts-synthesize-text.md",
        _DOCS + "tts-synthesize-text-via-websocket.md",
        _DOCS + "tts-features.md",
    ]
    voices_docs = [_DOCS + "tts-supported-languages-and-voices.md"]
    stt_guidance = (
        "Return every SESTEK-family model name listed by the documented models endpoint of each cloud region "
        "(ModelName is the id); skip Whisper/Dolphin-family models. Only names ending in Stream are real-time."
    )
    tts_guidance = (
        "No model parameter: return one record per documented voice tier, languages from that tier's voices."
    )
    voices_guidance = (
        "Return every row of the voices table (Voice ID column is the exact id), compatible with its tier record; "
        "skip voices of externally developed models."
    )
