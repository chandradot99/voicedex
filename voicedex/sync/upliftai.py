"""
Uplift AI — Orator text-to-speech (Urdu and other Pakistani languages) and Scribe speech-to-text (beta).

Source: docs (docs.upliftai.org, Mintlify; OpenAPI at /api-reference/openapi.yml). Voices come from the
voices page, backed by the machine-readable https://docs.upliftai.org/voices.json. The TTS API has no
model parameter (one Orator engine, selected by voiceId). Pricing is a monthly subscription in TTS minutes
and STT credits, not a published per-unit money rate.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOCS = "https://docs.upliftai.org/"


class UpliftAISyncer(DocsOnlySyncer):
    provider_id = "upliftai"
    stt_docs = [_DOCS + "api-reference/endpoint/speech-to-text.md"]
    tts_docs = [
        _DOCS + "orator.md",
        _DOCS + "orator_limits.md",
        _DOCS + "websocket-tts.md",
        _DOCS + "api-reference/endpoint/text-to-speech.md",
    ]
    voices_docs = [_DOCS + "orator_voices.md", _DOCS + "voices.json"]
    stt_guidance = (
        "Return every model id in the speech-to-text endpoint's `model` enum, with the documented languages. "
        "Credit rates go in meta; no money price unless one is published per unit."
    )
    tts_guidance = (
        "The TTS API has no model parameter: return one model for the Orator engine. Output formats and the "
        "per-request character limit from the API reference."
    )
    voices_guidance = (
        "Return every voice in the catalog and the earlier-voices table (voice id = exact voiceId), with "
        "gender, age, accent, tags and language."
    )
