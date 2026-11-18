"""
Vatis Tech — speech-to-text via the Vatis Streams API (pre-recorded and real-time).

Source: docs (docs.vatis.tech, indexed by docs.vatis.tech/llms.txt) and the pricing page (vatis.tech/pricing,
EUR). The API has no model parameter or model-list endpoint (transcription is selected by stream configuration
template); the model name comes from the pricing page. Docs-only.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class VatisSyncer(DocsOnlySyncer):
    provider_id = "vatis"
    stt_docs = [
        "https://vatis.tech/pricing",
        "https://docs.vatis.tech/speech-to-text/pre-recorded/pre-recorded-transcription.md",
        "https://docs.vatis.tech/speech-to-text/pre-recorded/transcription-languages.md",
        "https://docs.vatis.tech/speech-to-text/real-time/real-time-transcription.md",
        "https://docs.vatis.tech/speech-to-text/real-time/transcription-languages.md",
    ]
    stt_guidance = (
        "Return each speech-to-text model Vatis names publicly (pricing page model names); record the stream "
        "configuration template ids in meta. Languages from the transcription-languages tables (pre-recorded "
        "vs real-time lists differ — keep the real-time list in meta unless the real-time API has its own "
        "named model). Prices in EUR (currency + price) per hour, only from vatis.tech/pricing."
    )
