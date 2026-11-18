"""
Modulate — Velma 2 speech-to-text (Multilingual, English Fast, Multilingual Fast), batch and streaming.

Source: docs (docs.modulate.ai STT API reference, indexed by docs.modulate.ai/llms.txt) and the pricing page
(modulate.ai/pricing, USD per hour of audio). Modulate exposes no model-list endpoint: each STT variant is its own
endpoint (velma-2-stt-batch*, velma-2-stt-streaming*), so docs-only.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class ModulateSyncer(DocsOnlySyncer):
    provider_id = "modulate"
    stt_docs = [
        "https://docs.modulate.ai/api-reference/stt/overview.md",
        "https://docs.modulate.ai/get-started/stt.md",
        "https://www.modulate.ai/pricing",
    ]
    stt_guidance = (
        "Return one model per speech-to-text product variant (each variant has a batch and/or streaming "
        "endpoint; record the endpoint URLs in meta.endpoints). Languages as BCP-47 only where listed; "
        "['*'] for variants described as multilingual without a list. Prices are USD per hour of audio from "
        "modulate.ai/pricing — batch as the base price, streaming as a variant; add-ons in notes. Detection, "
        "redaction and Velma triage products are not STT models — skip them."
    )
