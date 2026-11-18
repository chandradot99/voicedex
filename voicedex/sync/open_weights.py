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
