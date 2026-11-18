"""
KugelAudio — text-to-speech (Kugel 3 family), speech-to-text (Kugel Ear) and speech-to-speech (Kugel Fluid).

Source: docs (docs.kugelaudio.com models / feature pages, indexed by docs.kugelaudio.com/llms.txt) and the
pricing page (kugelaudio.com/pricing, EUR). GET /v1/models and GET /v1/voices exist but need an API key we
don't have, and the docs list only a few example voices — models docs-only, voices not synced until a key is added.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class KugelAudioSyncer(DocsOnlySyncer):
    provider_id = "kugelaudio"
    tts_docs = [
        "https://docs.kugelaudio.com/models.md",
        "https://docs.kugelaudio.com/api-reference/tts/audio-formats.md",
        "https://docs.kugelaudio.com/features/text-processing.md",
        "https://kugelaudio.com/pricing",
    ]
    stt_docs = [
        "https://docs.kugelaudio.com/models.md",
        "https://docs.kugelaudio.com/features/speech-to-text.md",
    ]
    sts_docs = [
        "https://docs.kugelaudio.com/models.md",
        "https://docs.kugelaudio.com/speech-to-speech/overview.md",
        "https://docs.kugelaudio.com/speech-to-speech/limits.md",
    ]
    tts_guidance = (
        "Return every current text-to-speech model id, plus legacy ids that carry their own published price "
        "(set meta.alias_of to the model they run on). Prices only from kugelaudio.com/pricing, in EUR "
        "(currency + price), per minute of generated audio. Languages from the supported-languages table."
    )
    stt_guidance = (
        "Return every speech-to-text model id with its listed languages, batch and streaming endpoints and "
        "per-request duration limit. Prices only if kugelaudio.com/pricing lists the model."
    )
    sts_guidance = (
        "Return every speech-to-speech (live voice agent) model id; lifecycle beta while the docs call the "
        "service a beta. Languages from the docs/changelog. Speech enhancement models are not STT/TTS — skip."
    )
