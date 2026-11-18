"""
Phonexia (Brno, Czechia) — Speech Platform 4 speech-to-text: the 6th Gen engine and Enhanced Speech to Text
Built on Whisper.

Source: docs (docs.phonexia.com, mirrored at docs.cloud.phonexia.com — the former blocks automated fetches).
Speech Platform 4 is on-premises software (virtual appliance REST API or gRPC microservices); the deployed
models are listed by each installation's Speech Platform Info endpoint, so there is no public list API.
No published pricing (models and licenses are supplied on request).
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_SP4 = "https://docs.phonexia.com/products/speech-platform-4/"


class PhonexiaSyncer(DocsOnlySyncer):
    provider_id = "phonexia"
    stt_docs = [
        _SP4 + "technologies/speech-to-text/supported-languages",
        _SP4 + "technologies/speech-to-text/phonexia-speech-to-text",
        _SP4 + "technologies/speech-to-text/enhanced-speech-to-text-built-on-whisper",
        _SP4 + "rest/api/speech-to-text-by-phonexia",
        _SP4 + "rest/api/enhanced-speech-to-text-built-on-whisper",
        _SP4 + "microservices/audio-formats",
    ]
    stt_guidance = (
        "Return one model per speech-to-text technology, keyed by its technology identifier as used in the "
        "Speech Platform Info endpoint. Languages from that technology's column of the supported-languages "
        "table (union across engine versions; per-version lists in meta). Batch tasks over REST/gRPC are not "
        "streaming. No default and no pricing unless Phonexia publishes them."
    )
