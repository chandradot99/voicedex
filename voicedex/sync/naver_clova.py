"""
Naver Cloud Platform — CLOVA Speech / CLOVA Speech Recognition (CSR) speech-to-text and CLOVA Voice
text-to-speech.

Source: docs (api.ncloud-docs.com English API guides, guide.ncloud-docs.com spec pages). There is no model
parameter or model-list API: each STT "model" is one recognition API (CLOVA Speech long-sentence, short-
sentence and gRPC streaming recognition, plus the separate CSR short-utterance API), and CLOVA Voice is a
single TTS (Premium) API whose speaker ids are documented in its reference. Prices are KRW from the
ncloud.com product pages, which load them from www.ncloud.com/api/fees/price/{KR|COM}/KRW.
"""

from voicedex.sync.docs_only import DocsOnlySyncer

_API = "https://api.ncloud-docs.com/docs/en/"


class NaverClovaSyncer(DocsOnlySyncer):
    provider_id = "naver-clova"
    stt_docs = [
        _API + "ai-application-service-clovaspeech",
        _API + "ai-application-service-clovaspeech-longsentence",
        _API + "ai-application-service-clovaspeech-shortsentence",
        _API + "ai-application-service-clovaspeech-grpc",
        _API + "ai-naver-clovaspeechrecognition-stt",
        "https://guide.ncloud-docs.com/docs/en/clovaspeech-spec",
        "https://www.ncloud.com/product/aiService/clovaSpeech",
        "https://www.ncloud.com/product/aiService/csr",
    ]
    tts_docs = [
        _API + "ai-naver-clovavoice",
        _API + "ai-naver-clovavoice-ttspremium",
        "https://guide.ncloud-docs.com/docs/en/clovavoice-spec",
        "https://www.ncloud.com/product/aiService/clovaVoice",
    ]
    voices_docs = [_API + "ai-naver-clovavoice-ttspremium"]
    stt_guidance = (
        "There is no model parameter: return one model per recognition API (CLOVA Speech long-sentence, "
        "short-sentence, streaming, and CSR), with the languages each API's language parameter accepts. "
        "Prices are KRW per 15 seconds on the Basic plan; express them per minute in KRW (currency + price)."
    )
    tts_guidance = (
        "CLOVA Voice exposes one TTS API (Premium plan); return it as one model. Price is KRW per 1,000 "
        "characters beyond the plan's included characters; record it per character in KRW."
    )
    voices_guidance = (
        "Return every speaker id in the CLOVA Voice speaker table with its name, language and gender "
        "(child voices: gender as stated, age child). Mark emotion only for speakers the emotion parameter "
        "lists. compatible_models = the single TTS model."
    )
