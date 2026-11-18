"""
Zyphra — ZONOS text-to-speech on Zyphra Cloud (OpenAI-compatible /api/v1/audio/speech).

Source: docs. Zyphra's public model list (https://api.zyphracloud.com/api/v1/models, no key needed) carries
each model's licence, Hugging Face link and price per 1M UTF-8 bytes; the zyphra.com model posts and the
Hugging Face model cards give languages and features. Stock voices are listed only behind an authenticated
endpoint (audio/default-voices), so voices are not synced.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class ZyphraSyncer(DocsOnlySyncer):
    provider_id = "zyphra"
    tts_docs = [
        "https://api.zyphracloud.com/api/v1/models",
        "https://www.zyphra.com/models",
        "https://www.zyphra.com/our-work/zonos3-mini",
        "https://www.zyphra.com/our-work/zonos2",
    ]
    tts_guidance = (
        "Return every TTS model in the Zyphra Cloud model list (type Audio, main use case TTS); model_id = its "
        "id. Price = audioPricePerMillionUtf8Bytes converted to a per-byte price_usd. open_weights from the "
        "licence and Hugging Face link. Languages from the model card; models no longer served are excluded."
    )
