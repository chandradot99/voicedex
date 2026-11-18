"""
Phonic — speech-to-speech models for voice agents.

Source: docs (docs.phonic.ai; llms.txt, the OpenAPI spec at docs.phonic.ai/openapi.json, the Voices and Supported
Languages pages) plus phonic.ai/pricing. `GET /v1/voices` exists but needs a key — docs-only until a key is added.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_BASE = "https://docs.phonic.ai"


class PhonicSyncer(DocsOnlySyncer):
    provider_id = "phonic"
    sts_docs = [
        f"{_BASE}/docs/get-started/overview.md",
        f"{_BASE}/api-reference/agents/create.md",
        f"{_BASE}/docs/build/agents/supported_languages.md",
        "https://phonic.ai/pricing",
    ]
    voices_docs = [f"{_BASE}/docs/build/agents/voices.md"]
    sts_guidance = (
        "Return every speech-to-speech model id accepted by the agent `model` field (OpenAPI enum). Exclude "
        "models documented as deprecated without a shutdown date. Languages from the Supported Languages page. "
        "Per-minute price only from phonic.ai's own pricing page (plans as variants)."
    )
    voices_guidance = (
        "Return the base voices table (exact voice ids), with gender, accent (lowercase) and style as description."
    )
