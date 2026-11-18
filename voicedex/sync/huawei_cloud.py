"""
Huawei Cloud SIS (Speech Interaction Service) — Real-Time ASR, Short Sentence Recognition and Real-Time TTS,
international site.

Source: docs (support.huaweicloud.com/intl/en-us, API Reference `api-sis` and Service Overview `productdesc-sis`).
There is no model-list API. STT "models" are the `property` strings (Language_SamplingRate_Domain) accepted by
the Real-Time ASR WebSocket API and the Short Sentence Recognition HTTP API; one model per property, with the
APIs that accept it in meta. Real-Time TTS has no model id — the `property` value selects the speaker — so the
TTS endpoint is one model and every documented speaker property is a voice. Prices come from the international
price calculator (huaweicloud.com/intl/en-us/pricing/calculator.html#/sis), which is rendered client-side. The
mainland site (support.huaweicloud.com without /intl) documents a larger, separately priced catalog; this
syncer follows the international site.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_API = "https://support.huaweicloud.com/intl/en-us/api-sis/"
_DESC = "https://support.huaweicloud.com/intl/en-us/productdesc-sis/"
_PRICE = "https://www.huaweicloud.com/intl/en-us/pricing/calculator.html#/sis"


class HuaweiCloudSyncer(DocsOnlySyncer):
    provider_id = "huawei-cloud"
    stt_docs = [
        _API + "sis_03_0030.html",   # Real-Time ASR — Starting Recognition (property table)
        _API + "sis_03_0094.html",   # Short Sentence Recognition — HTTP interface (property table)
        _API + "sis_03_0004.html",   # Endpoints (regions)
        _DESC + "sis_01_0008.html",  # RASR restrictions
        _PRICE,
    ]
    tts_docs = [
        _API + "sis_03_0115.html",   # Real-Time TTS — Request for Starting TTS (speaker properties)
        _DESC + "sis_01_0051.html",  # Real-Time TTS restrictions
        _PRICE,
    ]
    voices_docs = [_API + "sis_03_0115.html"]
    stt_guidance = (
        "Return one model per `property` value documented for the international Real-Time ASR and Short "
        "Sentence Recognition APIs (union; record which APIs accept it in meta). Skip properties the docs say "
        "are old/unmaintained with no shutdown date. Price from the international calculator: real-time per "
        "hour as the main price, short-sentence per call as a variant; keep volume tiers in notes."
    )
    tts_guidance = (
        "Real-Time TTS has no model id; return one model for the Real-Time TTS endpoint with its languages, "
        "sample rates, formats, text limit and per-call price (state the characters-per-call rule in notes)."
    )
    voices_guidance = (
        "Return every speaker `property` value in the international Real-Time TTS property table with its "
        "display name and language; gender only when the value or docs state it."
    )
