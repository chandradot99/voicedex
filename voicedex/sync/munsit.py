"""
Munsit (CNTXT AI) — Arabic speech-to-text and Faseeh text-to-speech.

Source: docs (docs.munsit.com; every page is also served as Markdown, full corpus at /llms-full.txt).
`GET /api/v1/models` (TTS models only) and `GET /api/v1/voices` exist but need an API key — docs-only until a
key is added. STT models have no discovery endpoint; they are documented on the speech-to-text pages. The docs
list featured voices by display name only (voice ids are opaque and only returned by the voices API), so voices
are not synced from docs.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class MunsitSyncer(DocsOnlySyncer):
    provider_id = "munsit"
    stt_docs = [
        "https://docs.munsit.com/speech-to-text/get-started.md",
        "https://docs.munsit.com/speech-to-text/transcribe.md",
        "https://docs.munsit.com/speech-to-text/streaming.md",
    ]
    tts_docs = [
        "https://docs.munsit.com/text-to-speech/models.md",
        "https://docs.munsit.com/text-to-speech/synthesize.md",
        "https://docs.munsit.com/reference/websocket.md",
    ]
    stt_guidance = (
        "Return every speech-to-text model id accepted in the `model` field of the batch and live streaming "
        "endpoints. Pricing is in credits: record the credit rate in pricing notes and set a USD price only "
        "where the docs publish one per unit (e.g. per hour of audio)."
    )
    tts_guidance = (
        "Return every text-to-speech model_id from the models page. Credit pricing goes in meta unless a "
        "per-character money price is published."
    )
