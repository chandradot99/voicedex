"""
Cohere — Cohere Transcribe speech-to-text (v2 Audio Transcriptions API).

Source: docs (docs.cohere.com Transcribe model pages, API reference, rate limits). No public model-list
endpoint that we sync (GET /v1/models needs a key — docs-only until a key is added). The API is free with
trial rate limits; production runs on a dedicated Model Vault priced per hour-instance via sales, so no
per-unit price is published.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class CohereSyncer(DocsOnlySyncer):
    provider_id = "cohere"
    stt_docs = [
        "https://docs.cohere.com/docs/transcribe",
        "https://docs.cohere.com/docs/transcribe-arabic",
        "https://docs.cohere.com/reference/create-audio-transcription",
        "https://docs.cohere.com/docs/rate-limits",
    ]
    stt_guidance = (
        "Return every Transcribe model id callable on the Audio Transcriptions API. Languages as BCP-47 from "
        "the model page. Weights are open on Hugging Face (CohereLabs org): set open_weights with the licence. "
        "Pricing only if Cohere publishes a per-unit number (Model Vault hour-instance pricing is via sales)."
    )
