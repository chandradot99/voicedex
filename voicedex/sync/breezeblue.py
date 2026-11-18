"""
BreezeBlue: Breeze TTS hosted API and open weights (non-commercial licence).

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class BreezeBlueSyncer(DocsOnlySyncer):
    provider_id = "breezeblue"
    tts_docs = [
        "https://docs.breezeblue.ai/llms.txt",
        "https://breezeblue.ai/pricing",
        "https://huggingface.co/BreezeBlue",
    ]
    tts_guidance = (
        "One record per hosted/open model. open_weights from the HF repo licence (commercial_use=false for "
        "non-commercial). Prices only from the vendor's own page."
    )
