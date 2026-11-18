"""
Open-weights publishers synced from the Hugging Face Hub (see voicedex/sync/huggingface.py).

One class per org that clears the inclusion bar in docs/design/provider-expansion.md §1 and has no
first-party hosted API of its own (orgs that sell an API get the open-weights section on their own
provider instead).
"""

from voicedex.sync.huggingface import HuggingFaceSyncer


class HexgradSyncer(HuggingFaceSyncer):
    provider_id = "hexgrad"
    hf_authors = ["hexgrad"]


class KyutaiSyncer(HuggingFaceSyncer):
    provider_id = "kyutai"
    hf_authors = ["kyutai"]


class OpenBMBSyncer(HuggingFaceSyncer):
    provider_id = "openbmb"
    hf_authors = ["openbmb"]


class K2FsaSyncer(HuggingFaceSyncer):
    provider_id = "k2-fsa"
    hf_authors = ["k2-fsa"]


class AI4BharatSyncer(HuggingFaceSyncer):
    provider_id = "ai4bharat"
    hf_authors = ["ai4bharat"]


class CanopyLabsSyncer(HuggingFaceSyncer):
    provider_id = "canopylabs"
    hf_authors = ["canopylabs"]


class SesameSyncer(HuggingFaceSyncer):
    provider_id = "sesame"
    hf_authors = ["sesame"]


class MicrosoftSyncer(HuggingFaceSyncer):
    provider_id = "microsoft"
    hf_authors = ["microsoft"]


class SWividSyncer(HuggingFaceSyncer):
    provider_id = "swivid"
    hf_authors = ["SWivid"]


class FunAudioLLMSyncer(HuggingFaceSyncer):
    provider_id = "funaudiollm"
    hf_authors = ["FunAudioLLM"]


class ResembleOpenSyncer(HuggingFaceSyncer):
    provider_id = "resemble"
    hf_authors = ["ResembleAI"]


class CoquiOpenSyncer(HuggingFaceSyncer):
    provider_id = "coqui"
    hf_authors = ["coqui"]


class HumeOpenSyncer(HuggingFaceSyncer):
    provider_id = "humeai"
    hf_authors = ["HumeAI"]


# ── 2026-11 gap pass (reports: research_notes/Missed voice AI providers) ──

class OpenMOSSSyncer(HuggingFaceSyncer):
    provider_id = "openmoss"
    hf_authors = ["OpenMOSS-Team"]


class KittenMLSyncer(HuggingFaceSyncer):
    # Stellon Labs also sells a hosted OpenAI-compatible API.
    provider_id = "kittenml"
    hf_authors = ["KittenML"]
    tts_docs = [
        "https://docs.kittenml.com/models",
        "https://docs.kittenml.com/tts/generate-speech",
        "https://kittenml.com/#pricing",
    ]
    tts_guidance = (
        "Hosted API models only (the open-weights repos come from Hugging Face): one record per callable model id "
        "of the hosted TTS API, with published per-unit prices; set open_weights when the hosted model is the "
        "same as a published repo."
    )
    stt_docs = [
        "https://docs.kittenml.com/models",
        "https://docs.kittenml.com/stt/upload-transcription",
        "https://docs.kittenml.com/stt/language-hints",
        "https://kittenml.com/#pricing",
    ]
    stt_guidance = "Hosted speech-to-text models only; same rules as TTS (aliases in meta)."


class NariLabsSyncer(HuggingFaceSyncer):
    provider_id = "nari-labs"
    hf_authors = ["nari-labs"]


class MyShellSyncer(HuggingFaceSyncer):
    provider_id = "myshell-ai"
    hf_authors = ["myshell-ai"]


class IndexTTSSyncer(HuggingFaceSyncer):
    provider_id = "index-tts"
    hf_authors = ["IndexTeam"]


class RVCBossSyncer(HuggingFaceSyncer):
    # GPT-SoVITS weights are published from the maintainer's personal account.
    provider_id = "rvc-boss"
    hf_authors = ["lj1995"]


class SunoSyncer(HuggingFaceSyncer):
    provider_id = "suno"
    hf_authors = ["suno"]


class ParlerTTSSyncer(HuggingFaceSyncer):
    provider_id = "parler-tts"
    hf_authors = ["parler-tts"]


class MayaResearchSyncer(HuggingFaceSyncer):
    # Also sells a hosted TTS API (Maya Studio).
    provider_id = "maya-research"
    hf_authors = ["maya-research"]
    tts_docs = [
        "https://docs.mayaresearch.ai/reference/models",
        "https://docs.mayaresearch.ai/api-reference/tts",
        "https://www.mayaresearch.ai/llm.txt",
    ]
    tts_guidance = (
        "Hosted API models only (open-weights repos come from Hugging Face): one record per callable model id of "
        "the hosted TTS API; prices only if published per unit; regions from documented serving regions."
    )


class TwoNoiseSyncer(HuggingFaceSyncer):
    # ChatTTS is tagged text-to-audio, not text-to-speech.
    provider_id = "2noise"
    hf_authors = ["2Noise"]
    extra_pipelines = {"text-to-audio": "tts"}


class SberOpenSyncer(HuggingFaceSyncer):
    # SaluteSpeech stopped selling, but Sber's GigaAM ASR weights are published under ai-sage.
    provider_id = "sber-salutespeech"
    hf_authors = ["ai-sage"]


class SupertoneOpenSyncer(HuggingFaceSyncer):
    provider_id = "supertone"
    hf_authors = ["Supertone"]
