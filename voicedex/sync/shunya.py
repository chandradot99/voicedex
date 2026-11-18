"""
Shunya Labs — Horizon speech-to-text and Radiance text-to-speech (Indic-first, plus universal models).

Source: docs (www.shunyalabs.ai/docs: Horizon models page, capability matrix, Radiance overview / voices /
audio formats) and the public pricing page (www.shunyalabs.ai/pricing). There is no public model-list
endpoint; GET /languages on the ASR gateway needs an access token we don't have — docs-only until a key is added.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_SITE = "https://www.shunyalabs.ai"


class ShunyaSyncer(DocsOnlySyncer):
    provider_id = "shunya"
    stt_docs = [
        _SITE + "/docs/horizon/models-x9jt",
        _SITE + "/docs/horizon/overview-dp3f",
        _SITE + "/docs/horizon/features-jsw1",
        _SITE + "/docs/get-started/capability-matrix-z0f0",
        _SITE + "/docs/get-started/supported-languages-vy4d",
        _SITE + "/pricing",
    ]
    tts_docs = [
        _SITE + "/docs/radiance/overview-g7we",
        _SITE + "/docs/radiance/voices-4sa1",
        _SITE + "/docs/radiance/audio-formats-r8rp",
        _SITE + "/pricing",
    ]
    voices_docs = [_SITE + "/docs/radiance/voices-4sa1"]
    stt_guidance = (
        "Return every speech-recognition model id the API accepts in the `model` field (current ids, not the "
        "legacy aliases the docs say still work — note those in meta). Per-minute USD price from the pricing "
        "page (pay-as-you-go; volume rate as a variant). Open weights only where a downloadable model repo "
        "with a stated licence is named as the same model."
    )
    tts_guidance = (
        "Return every text-to-speech model id from the Radiance models table. Price per character from the "
        "pricing page, only for models it lists."
    )
    voices_guidance = (
        "Return every named voice in the voice catalogue (voice id = the exact `voice` string), with gender "
        "and native language; record which models the named voices apply to."
    )
