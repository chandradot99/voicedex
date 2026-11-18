"""
AmiVoice API (Advanced Media, Inc.) — Japanese-focused cloud speech recognition.

Source: docs (docs.amivoice.com Markdown manual, indexed by docs.amivoice.com/llms.txt) and the price page
on acp.amivoice.com. Models are the connection-engine names (`grammarFileNames`) listed in the engine
table; engines marked as AmiVoice API Private only are a separate product and are excluded. No list API.
Prices are JPY (tax included) per hour/second of detected speech, by engine category.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_MANUAL = "https://docs.amivoice.com/amivoice-api/manual/"


class AmiVoiceSyncer(DocsOnlySyncer):
    provider_id = "amivoice"
    stt_docs = [
        _MANUAL + "engines.md",
        _MANUAL + "supported-languages.md",
        _MANUAL + "audio-format.md",
        _MANUAL + "limitations.md",
        _MANUAL + "speaker-diarization.md",
        "https://acp.amivoice.com/amivoice_api/price/",
    ]
    stt_guidance = (
        "Return every public connection-engine name (grammarFileNames) in the engine table as one model; skip "
        "engines available only on AmiVoice API Private. Sample rates per the engine's 8k/16k support and the "
        "audio-format page. Price: JPY per hour (currency + price) for the engine's category from the price "
        "page, no-log realtime/sync price as the main price, other interface/log options as variants."
    )
