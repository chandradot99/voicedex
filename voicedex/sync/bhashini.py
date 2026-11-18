"""
Bhashini (Digital India Bhashini Division, MeitY, Government of India) — ULCA / Dhruva speech APIs.

Source: docs (dibd-bhashini.gitbook.io/bhashini-apis; the older bhashini.gitbook.io/bhashini-apis copy lacks the
model table). Bhashini routes every request through a *pipeline* (pipeline search → pipeline config → pipeline
compute); the config call resolves, per task and language, a ``serviceId`` that the compute call
(dhruva-api.bhashini.gov.in) takes. That ``serviceId`` is the stable, user-facing handle for one hosted model
family (e.g. one AI4Bharat or IIT Madras ASR service covering several languages), so **one catalog model = one
ASR/TTS serviceId**, with the languages that service is documented to support; ULCA's internal per-language
``modelId`` hashes are not catalogued. Voices are not catalogued either: TTS services only take a generic
``gender`` (male/female) parameter. The pipeline search/config endpoints are machine-readable, but they need an
integrator ``userID`` + ``ulcaApiKey`` from ULCA registration that we do not have — docs-only until a key is added.
Free API usage is restricted to proofs of concept; production/paid use goes through the Bhashini team, so no
prices are published.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_DOCS = "https://dibd-bhashini.gitbook.io/bhashini-apis"


class BhashiniSyncer(DocsOnlySyncer):
    provider_id = "bhashini"
    stt_docs = [
        f"{_DOCS}/available-models-for-usage",
        f"{_DOCS}/pipeline-compute-call/request-payload",
        f"{_DOCS}/websocket-asr-api",
    ]
    tts_docs = [
        f"{_DOCS}/available-models-for-usage",
        f"{_DOCS}/pipeline-compute-call/request-payload",
    ]
    stt_guidance = (
        "One model per ASR Service ID in the 'Available Models for usage' table (model_id = the exact "
        "serviceId string). Languages = that row's languages as ISO-639 codes (use script subtags only "
        "where the docs name a script). Put the model provider institute in meta.model_provider. "
        "Streaming only if the docs tie the service to the WebSocket ASR API. No pricing (PoC-only terms)."
    )
    tts_guidance = (
        "One model per TTS Service ID in the TTS and Voice Cloning tables (model_id = the exact serviceId). "
        "Languages = that row's languages as ISO-639 codes (script subtags where the docs name a script). "
        "voice_cloning only for services listed under Voice Cloning. Gender options go in meta. No pricing."
    )
