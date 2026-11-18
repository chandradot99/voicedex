"""
ReadSpeaker — speechCloud API (SCAPI): cloud REST text-to-speech with licensed per-language voices.

Source: docs. The public SCAPI Product Specification PDF (docs.readspeaker.com) gives parameters, formats and
limits; implementation docs live in the logged-in customer portal. The voice catalog comes from the public
per-language pages under readspeaker.com/languages-voices/ (each has a "Technical details" table: voice, gender,
technology, engine provider, availability), which the spec names as the published list of available voices.
Only voices marked available in "Cloud" are relevant. SCAPI has a REST call returning the languages/voices
licensed to an account, but it needs a customer API key — docs-only until one is added. No public prices
(credits = characters, sold via account managers).
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_SITE = "https://www.readspeaker.com/"


class ReadSpeakerSyncer(DocsOnlySyncer):
    provider_id = "readspeaker"
    tts_docs = [
        "https://docs.readspeaker.com/assets/speechcloudapi/ps/LATEST_VERSION",
        _SITE + "products/speechcloud-api/",
        _SITE + "languages-voices/",
    ]
    voices_docs = [
        _SITE + "sitemap-0.xml",
        _SITE + "languages-voices/",
    ]
    tts_guidance = (
        "SCAPI has no model parameter: return one model for the speechCloud API with the languages of all "
        "Cloud-available voices, the documented audio formats, sample rates and per-request text limit. "
        "No price unless ReadSpeaker publishes a per-unit number."
    )
    voices_guidance = (
        "Follow every /languages-voices/<language>/ page listed in the sitemap and read its technical-details "
        "table. Return each voice available in Cloud; voice_id is the voice= value of its demo link. When one "
        "name is used in several languages, return one voice carrying all of those languages and keep the "
        "per-language engine details in meta. Keep the engine provider and technology in meta."
    )
