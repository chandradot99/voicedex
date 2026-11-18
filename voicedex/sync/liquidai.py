"""
Liquid AI (Cambridge, MA) — LFM audio foundation models: hosted API (per-token) and open weights on Hugging Face (lfm1.0 licence).

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class LiquidAISyncer(DocsOnlySyncer):
    provider_id = "liquidai"
    sts_docs = [
        "https://docs.liquid.ai/lfm/key-concepts/audio-capabilities",
        "https://docs.liquid.ai/api/guides/audio",
        "https://www.liquid.ai/pricing?view=api",
        "https://huggingface.co/LiquidAI",
    ]
    sts_guidance = (
        "One record per current LFM audio model (speech in and speech out). Set open_weights {license, url, "
        "commercial_use} from the Hugging Face repo; the lfm1.0 licence is free for commercial use only under "
        "a revenue cap, so commercial_use=null and state the cap in meta.license_terms. Hosted per-token "
        "prices only if the pricing page lists that model."
    )
