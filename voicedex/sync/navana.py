"""
Navana.ai — Bodhi API platform: per-language speech-to-text models and text-to-speech for Indian languages.

Source: docs (docs.navana.ai; full corpus at https://docs.navana.ai/llms-full.txt). No public model or
voice list endpoint. Rates are shown only inside the logged-in platform (platform.navana.ai fetches them
from an authenticated pricing endpoint); the TTS list price comes from Navana's launch announcement.
The TTS API has no model parameter (one backend per language).
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOCS = "https://docs.navana.ai/"


class NavanaSyncer(DocsOnlySyncer):
    provider_id = "navana"
    stt_docs = [
        _DOCS + "speech-to-text/models/index.md",
        _DOCS + "speech-to-text/advanced-features/index.md",
        _DOCS + "concepts/audio-formats/index.md",
    ]
    tts_docs = [
        _DOCS + "text-to-speech/index.md",
        _DOCS + "text-to-speech/non-streaming/index.md",
        _DOCS + "text-to-speech/voices/index.md",
    ]
    voices_docs = [_DOCS + "text-to-speech/voices/index.md"]
    stt_guidance = (
        "Return every transcription model id in the Models and languages table; each model serves one "
        "language, so set languages from its row. No default unless the docs name one."
    )
    tts_guidance = (
        "Synthesis has no model parameter: return one model for the Bodhi TTS engine with the documented "
        "languages, sample rates and encodings. INR price per character only if Navana publishes one."
    )
    voices_guidance = (
        "Return every voice id in the voices table (exact id string); every voice speaks all synthesis "
        "languages."
    )
