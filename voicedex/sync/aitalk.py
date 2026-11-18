"""
AI Inc. (Tokyo) AITalk WebAPI: Japanese TTS, contract plans.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class AITalkSyncer(DocsOnlySyncer):
    provider_id = "aitalk"
    tts_docs = [
        "https://www.ai-j.jp/products/cloud_webapi/",
        "https://prtimes.jp/main/html/rd/p/000000151.000099620.html",
    ]
    tts_guidance = (
        "One record per synthesis engine/model generation callable via the WebAPI. No prices unless published "
        "per unit."
    )
