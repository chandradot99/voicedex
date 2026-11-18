"""
Boson AI — Higgs TTS (text-to-speech) and Higgs Realtime (speech-to-speech).

Source: docs (docs.boson.ai; llms.txt, the OpenAPI spec at docs.boson.ai/openapi.json and the pricing page,
which mirrors boson.ai/pricing). There is no model-list endpoint; `GET /v1/audio/voices` lists voices but needs
a key — docs-only until a key is added. Open TTS weights are on Hugging Face (bosonai/*) under a research /
non-commercial licence. Realtime input transcription (an STT model id) is only usable inside a Realtime session,
so it is recorded in the Realtime model's meta rather than as a standalone STT model.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_BASE = "https://docs.boson.ai"


class BosonAISyncer(DocsOnlySyncer):
    provider_id = "bosonai"
    tts_docs = [
        f"{_BASE}/llms.txt",
        f"{_BASE}/models/higgs-tts/overview.md",
        f"{_BASE}/models/higgs-tts/languages.md",
        f"{_BASE}/api-reference/audio/create-a-speech.md",
        f"{_BASE}/pricing.md",
    ]
    sts_docs = [
        f"{_BASE}/models/higgs-realtime/overview.md",
        f"{_BASE}/models/higgs-realtime/guides/connections-and-sessions.md",
        f"{_BASE}/models/higgs-realtime/guides/audio-and-voices.md",
        f"{_BASE}/pricing.md",
    ]
    voices_docs = [f"{_BASE}/models/higgs-tts/voices.md"]
    tts_guidance = (
        "Return every TTS model id accepted by POST /v1/audio/speech (the `model` enum in the OpenAPI spec). "
        "Languages from the Languages page / Hugging Face model card. Pricing per character from the pricing "
        "page. If the weights are on Hugging Face, set open_weights with the exact licence name and whether "
        "it permits commercial use."
    )
    sts_guidance = (
        "Return every speech-to-speech (Realtime) model id accepted in session.update. Token prices per token; "
        "per-minute estimates as variants. Put the input-transcription model id in meta, not as an STT model."
    )
    voices_guidance = "Return the preset voices listed on the Voices page (exact `voice` ids), usable with every TTS model."
