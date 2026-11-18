"""
Yandex SpeechKit (Yandex AI Studio) — speech recognition, synthesis and Realtime API voice models.

Source: docs (aistudio.yandex.ru/docs/en/speechkit; the old yandex.cloud/en/docs/speechkit URLs redirect there).
Recognition models are version tags documented on stt/models, synthesis models and voices on tts/models and
tts/voices, Realtime API voice models on the AI Studio common-instance models page. USD prices come from the
English pricing pages (international billing). There is no public model-list endpoint for speech models.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_BASE = "https://aistudio.yandex.ru/docs/en"


class YandexSyncer(DocsOnlySyncer):
    provider_id = "yandex"
    stt_docs = [
        f"{_BASE}/speechkit/stt/models",
        f"{_BASE}/speechkit/stt/",
        f"{_BASE}/speechkit/formats",
        f"{_BASE}/speechkit/concepts/limits",
        f"{_BASE}/speechkit/pricing",
    ]
    tts_docs = [
        f"{_BASE}/speechkit/tts/models",
        f"{_BASE}/speechkit/tts/",
        f"{_BASE}/speechkit/concepts/limits",
        f"{_BASE}/speechkit/pricing",
        f"{_BASE}/ai-studio/concepts/generation/models",
    ]
    sts_docs = [
        f"{_BASE}/ai-studio/concepts/generation/models",
        f"{_BASE}/ai-studio/concepts/agents/realtime",
        f"{_BASE}/ai-studio/pricing",
    ]
    voices_docs = [f"{_BASE}/speechkit/tts/voices"]
    stt_guidance = (
        "Return each recognition model value/version tag callable via the `model` field (main, release-candidate "
        "and deferred variants). Skip the 'deprecated' tag (no shutdown date). Languages from the supported-languages "
        "list. Prices are per 15-second unit in USD: express as per-minute (x4, exact) and quote the original in notes."
    )
    tts_guidance = (
        "Return each synthesis model (SpeechKit API v1/v3 models and their release-candidate tags, plus Realtime API "
        "models that only synthesize text). Skip the 'deprecated' tag. USD prices: v1 per 1M characters, v3 per "
        "250-character request unit — convert to per-character exactly and quote the original in notes."
    )
    sts_guidance = (
        "Return the Realtime API voice models (audio in, audio out) listed on the common-instance models page, with "
        "the model URI in meta. Mark models labelled experimental as alpha. Audio and token prices from the AI "
        "Studio pricing page (voice agents / Realtime sections), USD."
    )
    voices_guidance = (
        "Return every voice from the general-model and LiveTTS tables. Put roles (default first), supported API "
        "versions and voice family in meta; compatible_models = the synthesis/realtime models that accept that family."
    )
