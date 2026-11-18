"""
iApp Technology (Bangkok, Thailand) — Chinda ASR / OpenThai ASR speech-to-text and Chinda TTS text-to-speech.

Source: docs (iapp.co.th/en/docs, server-rendered; the machine-readable catalogue at
https://iapp.co.th/api-catalog.json and https://iapp.co.th/llms.txt list every API with its IC price). There is no
model- or voice-list endpoint: each model is its own endpoint path, so ids are the endpoint family names.
Prices are in IC (iApp Credits; 1 IC = THB 1.25, falling to THB 0.89 by top-up tier), which are not money per
unit — IC rates go in meta; a THB price is set only if iApp publishes one per unit.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class IappSyncer(DocsOnlySyncer):
    provider_id = "iapp"
    stt_docs = [
        "https://iapp.co.th/llms.txt",
        "https://iapp.co.th/en/docs/speech/speech-to-text/thai",
        "https://iapp.co.th/en/docs/speech/speech-to-text/realtime",
        "https://iapp.co.th/en/docs/speech/speech-to-text/english",
        "https://iapp.co.th/en/docs/speech/speech-to-text/chinese",
        "https://iapp.co.th/en/pricing",
    ]
    tts_docs = [
        "https://iapp.co.th/en/docs/speech/text-to-speech/text-to-speech-v3",
        "https://iapp.co.th/en/pricing",
    ]
    voices_docs = ["https://iapp.co.th/en/docs/speech/text-to-speech/text-to-speech-v3"]
    stt_guidance = (
        "One model per callable speech-to-text endpoint family listed in the Speech section of llms.txt / the "
        "API catalogue (each tier — base, pro, realtime — and each language endpoint is its own model). Skip tiers "
        "whose docs say they have ended or are now answered by another model. Prices are in IC credits: put the IC "
        "rate in meta; no money pricing unless a THB per-unit price is published."
    )
    tts_guidance = (
        "The current text-to-speech endpoint (not the deprecated V1/V2 endpoints, which have no shutdown date). "
        "Label alpha/beta only if the page says so. IC rates and monthly plans go in meta."
    )
    voices_guidance = (
        "The ready voices accepted by the `voice` parameter of the current TTS endpoint. Library reference clips "
        "used through the clone endpoint are not voice ids — note them in the model's meta instead."
    )
