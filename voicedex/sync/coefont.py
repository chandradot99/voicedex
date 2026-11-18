"""
CoeFont — Japanese AI voice platform; CoeFont API v2 text-to-speech.

Source: docs (docs.coefont.cloud ReDoc reference, coefont.cloud/llms.txt for plans). The API has no model
parameter: POST /v2/text2speech takes a CoeFont (voice) uuid, so the catalog records one TTS model.
GET /v2/coefonts/pro lists available CoeFont Pro voices but needs an HMAC-signed key — docs-only, without
voices, until a key is added. The API requires the Plus plan; no per-character API price is published.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class CoeFontSyncer(DocsOnlySyncer):
    provider_id = "coefont"
    tts_docs = [
        "https://docs.coefont.cloud/en/",
        "https://coefont.cloud/llms.txt",
    ]
    tts_guidance = (
        "The API has no model id; return one TTS model for the text2speech endpoint with its documented "
        "text limit, formats and parameters. Pricing only if a per-unit API price is published."
    )
