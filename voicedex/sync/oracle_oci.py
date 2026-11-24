"""
Oracle Cloud Infrastructure Speech: transcription and text-to-speech.

Source: docs (Claude Code extraction into .sync-cache/; see docs/design/extraction-spec.md).
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class OracleOCISyncer(DocsOnlySyncer):
    provider_id = "oracle-oci"
    stt_docs = [
        "https://docs.oracle.com/en-us/iaas/Content/speech/using/speech.htm",
        "https://docs.oracle.com/en-us/iaas/Content/speech/using/create-trans-job.htm",
        "https://docs.oracle.com/en-us/iaas/Content/speech/using/using-live-transcribe.htm",
        "https://docs.oracle.com/en-us/iaas/releasenotes/services/speech/",
        "https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/?currencyCode=USD",
    ]
    stt_guidance = (
        "One record per transcription model Oracle documents. OCI also serves third-party models (e.g. "
        "Whisper): include them only as Oracle-served models with meta.base_model naming the original; "
        "regions from the documented OCI regions mapped to us|eu|asia."
    )
    tts_docs = [
        "https://docs.oracle.com/en-us/iaas/Content/speech/using/speech.htm",
        "https://docs.oracle.com/en-us/iaas/Content/speech/using/using-tts.htm",
        "https://docs.oracle.com/en-us/iaas/Content/speech/using/using-realtime-tts-api.htm",
        "https://apexapps.oracle.com/pls/apex/cetools/api/v1/products/?currencyCode=USD",
    ]
    tts_guidance = (
        "One record per TTS model/voice engine. Note documented region restrictions in regions/meta."
    )
