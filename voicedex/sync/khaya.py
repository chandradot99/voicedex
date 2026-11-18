"""
Khaya AI (GhanaNLP) — Automatic Speech Recognition and Text-To-Speech APIs for Ghanaian and African languages.

Source: docs (developer.khaya.ai, an Azure API Management portal; translation.ghananlp.org redirects there).
The portal's per-API OpenAPI specs are the reference: ASR v3 (`/asr/v3`) and TTS v2 (`/tts/v2`). The APIs
have no model parameter — each API version is one model. ASR v3 lists its languages only via
GET /asr/v3/languages and TTS via GET /tts/v2/languages and /speakers, which need a subscription key we
don't have — docs-only until a key is added. Plans (per-call quotas) are on the portal's Products page.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_PORTAL = "https://developer.khaya.ai/"


class KhayaSyncer(DocsOnlySyncer):
    provider_id = "khaya"
    stt_docs = [_PORTAL + "apis", _PORTAL + "products"]
    tts_docs = [_PORTAL + "apis", _PORTAL + "products"]
    voices_docs = [_PORTAL + "apis"]
    stt_guidance = (
        "Return one model per Automatic Speech Recognition API version that is not marked deprecated "
        "(model_id = asr-<version>). Languages only from the official API spec; ISO 639-3 codes converted "
        "to the shortest BCP-47 form. Plans are per call quotas, not per-unit prices — keep them in meta."
    )
    tts_guidance = (
        "Return one model per Text-To-Speech API version that is not marked deprecated (model_id = "
        "tts-<version>), with the languages from the spec's language enum (shortest BCP-47 form)."
    )
    voices_guidance = (
        "Return every speaker_id from the current Text-To-Speech API spec; gender only when the id or docs "
        "state it. Speakers shared by all languages get languages ['*'] and compatible_models ['*']."
    )
