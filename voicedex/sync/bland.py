"""
Bland — Bland Speech text-to-speech (BTTS models), not Bland's phone-agent platform.

Source: docs (docs.bland.ai/tts/*, the API reference for /v2/tts, /v2/tts/ws, /v2/audio/speech and the model
manifests). Bland also publishes unauthenticated model listings (`GET https://api.bland.ai/v2/models`,
`GET https://api.bland.ai/v1/models`) that could back an API syncer later; `GET /v1/voices` needs a key, so
voices are the built-in voices documented in the docs — docs-only until a key is added.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_BASE = "https://docs.bland.ai"


class BlandSyncer(DocsOnlySyncer):
    provider_id = "bland"
    tts_docs = [
        f"{_BASE}/tts/welcome.md",
        f"{_BASE}/api-v2/get/tts-models.md",
        f"{_BASE}/api-v1/get/models.md",
        f"{_BASE}/api-v2/post/tts.md",
        f"{_BASE}/api-v2/post/audio-speech.md",
    ]
    voices_docs = [f"{_BASE}/tts/voices.md"]
    tts_guidance = (
        "Return every Bland Speech TTS model id from the model manifests (v2 ids as used by /v2/audio/speech; "
        "put the matching v1 engine id in meta). Per-character price from the Synthesize Speech billing note; "
        "note any launch discount and minimum charge."
    )
    voices_guidance = (
        "Return only the built-in voices documented as available to every organization (voice id = UUID). "
        "Skip cloned and public-library voices."
    )
