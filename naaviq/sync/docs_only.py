"""
Shared base for providers whose catalog data exists only in documentation.

Subclasses declare seed URLs + guidance per section; anything left empty is not synced.
Extraction is done by Claude Code into .sync-cache/ (see CLAUDE.md) — the AI parser only
calls the Anthropic API on a cache miss with ANTHROPIC_API_KEY set, which this project never does.
"""

from __future__ import annotations

import asyncio

from naaviq.sync.ai_parser import parse_models_from_docs, parse_voices_from_docs
from naaviq.sync.base import ProviderSyncer, SyncResult


class DocsOnlySyncer(ProviderSyncer):
    source = "docs"

    stt_docs: list[str] = []
    tts_docs: list[str] = []
    sts_docs: list[str] = []
    voices_docs: list[str] = []
    stt_guidance: str = ""
    tts_guidance: str = ""
    sts_guidance: str = ""
    voices_guidance: str = ""

    async def sync(self) -> SyncResult:
        async def models(kind: str, urls: list[str], guidance: str):
            if not urls:
                return []
            found, _ = await parse_models_from_docs(
                seed_urls=urls, provider_id=self.provider_id, model_type=kind, guidance=guidance)
            return found

        async def voices():
            if not self.voices_docs:
                return []
            found, _ = await parse_voices_from_docs(
                seed_urls=self.voices_docs, provider_id=self.provider_id, guidance=self.voices_guidance)
            return found

        stt, tts, sts, vs = await asyncio.gather(
            models("stt", self.stt_docs, self.stt_guidance),
            models("tts", self.tts_docs, self.tts_guidance),
            models("sts", self.sts_docs, self.sts_guidance),
            voices(),
        )
        docs = list(dict.fromkeys(self.stt_docs + self.tts_docs + self.sts_docs + self.voices_docs))
        return SyncResult(
            stt_models=stt, tts_models=tts, sts_models=sts, tts_voices=vs,
            source=self.source, docs_urls=docs,
            notes=f"docs: {len(stt)} STT, {len(tts)} TTS, {len(sts)} STS models, {len(vs)} voices.",
        )
