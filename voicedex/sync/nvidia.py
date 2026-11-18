"""
NVIDIA — Riva / Speech NIM speech models (ASR, TTS, speech-to-speech).

Source: docs. The hosted trial endpoints are listed on build.nvidia.com (explore/speech.md; per-model `.md`
model cards), and the self-hosted Speech NIM support matrices on docs.nvidia.com/nim/speech list containers,
languages and the Magpie voice names. Model ids are the build.nvidia.com publisher/name paths (NIM container
ids go in meta). Hosted calls go over gRPC (grpc.nvcf.nvidia.com) with a function id; there is no public
model-list or voice-list endpoint, and NVIDIA publishes no per-unit prices.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_NIM = "https://docs.nvidia.com/nim/speech/latest"
_BUILD = "https://build.nvidia.com"


class NvidiaSyncer(DocsOnlySyncer):
    provider_id = "nvidia"
    stt_docs = [
        f"{_BUILD}/explore/speech.md",
        f"{_NIM}/asr/index.html",
        f"{_NIM}/reference/support-matrix/asr.html",
    ]
    tts_docs = [
        f"{_BUILD}/explore/speech.md",
        f"{_NIM}/reference/support-matrix/tts.html",
    ]
    sts_docs = [f"{_BUILD}/explore/speech.md"]
    voices_docs = [f"{_NIM}/reference/support-matrix/tts.html"]
    stt_guidance = (
        "Return NVIDIA's own ASR models offered as a build.nvidia.com endpoint or a Speech NIM (skip third-party "
        "models such as OpenAI Whisper and generic legacy containers). model_id = the build.nvidia.com "
        "publisher/name path (nvidia/<name>); NIM container id in meta. Languages from the NIM support matrix. "
        "open_weights only when the model card links a Hugging Face repo (licence from that repo). No pricing."
    )
    tts_guidance = (
        "Return NVIDIA's own TTS models (skip third-party community models). model_id = build.nvidia.com "
        "publisher/name path. Languages from the NIM support matrix. No pricing."
    )
    sts_guidance = "Return NVIDIA's own speech-to-speech (full-duplex) models listed on build.nvidia.com."
    voices_guidance = (
        "Return each base built-in voice name exactly as the API takes it (no emotion suffix); list the "
        "emotion-suffixed variants in meta.emotions. compatible_models = the model the voice belongs to."
    )
