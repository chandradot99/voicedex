from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    data_dir: str = ""                     # catalog directory; empty = <repo>/data
    rate_limit: str = "100/minute"
    site_name: str = "Voicedex"
    site_url: str = "https://voicedex.dev"  # canonical origin for links, sitemap, share previews
    # Behind Cloudflare's proxy, the right-most X-Forwarded-For entry is a Cloudflare edge, not the
    # visitor. Set TRUST_CF_CONNECTING_IP=true only when all traffic comes through Cloudflare.
    trust_cf_connecting_ip: bool = False

    # Provider API keys — used by sync scripts
    deepgram_api_key: str = ""
    cartesia_api_key: str = ""
    elevenlabs_api_key: str = ""
    openai_api_key: str = ""
    google_cloud_api_key: str = ""
    sarvam_api_key: str = ""
    azure_speech_key: str = ""
    azure_speech_region: str = "eastus"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    hume_api_key: str = ""
    inworld_api_key: str = ""
    murf_api_key: str = ""
    speechmatics_api_key: str = ""
    lmnt_api_key: str = ""
    assemblyai_api_key: str = ""
    revai_api_key: str = ""
    gladia_api_key: str = ""
    minimax_api_key: str = ""
    ibm_tts_api_key: str = ""
    ibm_stt_api_key: str = ""
    neuphonic_api_key: str = ""
    resemble_api_key: str = ""
    fish_audio_api_key: str = ""
    unreal_speech_api_key: str = ""
    smallest_api_key: str = ""
    lovo_api_key: str = ""
    mistral_api_key: str = ""
    wellsaid_api_key: str = ""
    cambai_api_key: str = ""
    speechify_api_key: str = ""
    typecast_api_key: str = ""
    groq_api_key: str = ""
    soniox_api_key: str = ""
    xai_api_key: str = ""
    gradium_api_key: str = ""
    dashscope_api_key: str = ""        # Alibaba Cloud Model Studio — international (Singapore) key
    dashscope_workspace_id: str = ""   # Model Studio workspace id (models-list endpoint host)
    async_api_key: str = ""
    ibm_tts_url: str = "https://api.us-south.text-to-speech.watson.cloud.ibm.com"
    ibm_stt_url: str = "https://api.us-south.speech-to-text.watson.cloud.ibm.com"

    # AI parser key — used by sync scripts that parse docs (e.g., Cartesia models)
    anthropic_api_key: str = ""

    @property
    def data_path(self) -> Path:
        from voicedex.catalog.files import DEFAULT_DATA_DIR
        return Path(self.data_dir) if self.data_dir else DEFAULT_DATA_DIR


settings = Settings()
