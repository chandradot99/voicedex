"""
Single source of truth for the list of provider syncers.

Both `scripts/sync.py` and `voicedex-admin` consume this registry — any new
provider only needs to be registered here once.

Syncer classes are referenced by dotted path (module.Class) and loaded lazily
so importing this module stays cheap and doesn't pull in optional deps
(e.g., anthropic, provider SDKs) until a specific syncer is actually used.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Literal

from voicedex.sync.base import ProviderSyncer


@dataclass(frozen=True)
class SyncerEntry:
    provider_id: str
    display_name: str
    type: Literal["stt", "tts", "both"]
    syncer_path: str   # "voicedex.sync.deepgram.DeepgramSyncer"
    # Provider shut down its API / stopped selling: never synced; data/<id>/provider.json records why.
    retired: bool = False
    # Retired as an API seller but still publishing open weights: sync runs this syncer instead
    # (provider stays status=deprecated; its open-weights models stay active).
    open_weights_path: str | None = None

    @property
    def syncable(self) -> bool:
        return not self.retired or self.open_weights_path is not None


REGISTRY: list[SyncerEntry] = [
    SyncerEntry("deepgram",          "Deepgram",          "both", "voicedex.sync.deepgram.DeepgramSyncer"),
    SyncerEntry("cartesia",          "Cartesia",          "both", "voicedex.sync.cartesia.CartesiaSyncer"),
    SyncerEntry("elevenlabs",        "ElevenLabs",        "both", "voicedex.sync.elevenlabs.ElevenLabsSyncer"),
    SyncerEntry("openai",            "OpenAI",            "both", "voicedex.sync.openai.OpenAISyncer"),
    SyncerEntry("google-cloud",      "Google Cloud",      "both", "voicedex.sync.google_cloud.GoogleCloudSyncer"),
    SyncerEntry("sarvam",            "Sarvam",            "both", "voicedex.sync.sarvam.SarvamSyncer"),
    SyncerEntry("azure",             "Azure Speech",      "both", "voicedex.sync.azure.AzureSyncer"),
    SyncerEntry("amazon-polly",      "Amazon Polly",      "tts",  "voicedex.sync.amazon_polly.AmazonPollyDocsSyncer"),  # API path: AmazonPollySyncer
    SyncerEntry("humeai",            "Hume AI",           "tts",  "voicedex.sync.humeai.HumeAISyncer", retired=True, open_weights_path="voicedex.sync.open_weights.HumeOpenSyncer"),
    SyncerEntry("inworld",           "Inworld AI",        "both", "voicedex.sync.inworld.InworldAISyncer"),
    SyncerEntry("murf",              "Murf AI",           "tts",  "voicedex.sync.murf.MurfAISyncer"),
    SyncerEntry("speechmatics",      "Speechmatics",      "stt",  "voicedex.sync.speechmatics.SpeechmaticsSyncer"),
    SyncerEntry("lmnt",              "LMNT",              "tts",  "voicedex.sync.lmnt.LmntSyncer", retired=True),
    SyncerEntry("rime",              "Rime AI",           "tts",  "voicedex.sync.rime.RimeSyncer"),
    SyncerEntry("assemblyai",        "AssemblyAI",        "both", "voicedex.sync.assemblyai.AssemblyAISyncer"),
    SyncerEntry("revai",             "Rev AI",            "stt",  "voicedex.sync.revai.RevAISyncer"),
    SyncerEntry("gladia",            "Gladia",            "stt",  "voicedex.sync.gladia.GladiaSyncer"),
    SyncerEntry("minimax",           "MiniMax",           "tts",  "voicedex.sync.minimax.MinimaxSyncer"),
    SyncerEntry("ibm",               "IBM Watson",        "both", "voicedex.sync.ibm.IBMSyncer"),
    SyncerEntry("neuphonic",         "Neuphonic",         "tts",  "voicedex.sync.neuphonic.NeurophonicSyncer"),
    SyncerEntry("amazon-transcribe", "Amazon Transcribe", "stt",  "voicedex.sync.amazon_transcribe.AmazonTranscribeSyncer"),
    SyncerEntry("resemble",          "Resemble AI",       "tts",  "voicedex.sync.resemble.ResembleSyncer", retired=True, open_weights_path="voicedex.sync.open_weights.ResembleOpenSyncer"),
    SyncerEntry("fishaudio",         "Fish Audio",        "both", "voicedex.sync.fishaudio.FishAudioSyncer"),
    SyncerEntry("unrealspeech",      "Unreal Speech",     "tts",  "voicedex.sync.unrealspeech.UnrealSpeechSyncer"),
    SyncerEntry("smallestai",        "Smallest AI",       "both", "voicedex.sync.smallestai.SmallestAISyncer"),
    SyncerEntry("lovoai",            "Lovo AI",           "tts",  "voicedex.sync.lovoai.LovoAISyncer", retired=True),
    SyncerEntry("mistral",           "Mistral AI",        "both", "voicedex.sync.mistral.MistralSyncer"),
    SyncerEntry("wellsaid",          "WellSaid Labs",     "tts",  "voicedex.sync.wellsaid.WellSaidSyncer"),
    SyncerEntry("cambai",            "CAMB.ai",           "both", "voicedex.sync.cambai.CambAISyncer"),
    SyncerEntry("speechify",         "Speechify",         "tts",  "voicedex.sync.speechify.SpeechifySyncer"),
    SyncerEntry("typecastai",        "Typecast AI",       "tts",  "voicedex.sync.typecastai.TypecastAISyncer"),
    SyncerEntry("groq",              "Groq",              "both", "voicedex.sync.groq.GroqSyncer"),
    SyncerEntry("soniox",            "Soniox",            "both", "voicedex.sync.soniox.SonioxSyncer"),
    SyncerEntry("xai",               "xAI",               "both", "voicedex.sync.xai.XAISyncer"),
    SyncerEntry("gradium",           "Gradium",           "both", "voicedex.sync.gradium.GradiumSyncer"),
    SyncerEntry("alibaba",           "Alibaba Cloud Model Studio", "both", "voicedex.sync.alibaba.AlibabaSyncer"),
    SyncerEntry("meta",              "Meta",              "stt",  "voicedex.sync.meta.MetaSyncer"),
    SyncerEntry("async",             "Async",             "both", "voicedex.sync.asyncai.AsyncSyncer"),
    SyncerEntry("stepfun",           "StepFun",           "both", "voicedex.sync.stepfun.StepFunSyncer"),
    SyncerEntry("byteplus",          "BytePlus",          "both", "voicedex.sync.byteplus.BytePlusSyncer"),
    # ── Expansion 2026-11 (docs/design/provider-expansion.md) ──
    SyncerEntry('amazon-nova'      , 'Amazon Nova Sonic', 'sts', "voicedex.sync.amazon_nova.AmazonNovaSyncer"),
    SyncerEntry('nvidia'           , 'NVIDIA', 'both', "voicedex.sync.nvidia.NvidiaSyncer"),
    SyncerEntry('tencent'          , 'Tencent Cloud', 'both', "voicedex.sync.tencent.TencentSyncer"),
    SyncerEntry('iflytek'          , 'iFLYTEK', 'both', "voicedex.sync.iflytek.IflytekSyncer"),
    SyncerEntry('volcengine'       , 'Volcengine', 'both', "voicedex.sync.volcengine.VolcengineSyncer"),
    SyncerEntry('naver-clova'      , 'Naver CLOVA', 'both', "voicedex.sync.naver_clova.NaverClovaSyncer"),
    SyncerEntry('yandex'           , 'Yandex SpeechKit', 'both', "voicedex.sync.yandex.YandexSyncer"),
    SyncerEntry('zhipu'            , 'Zhipu AI (Z.ai)', 'both', "voicedex.sync.zhipu.ZhipuSyncer"),
    SyncerEntry('xiaomi'           , 'Xiaomi MiMo', 'both', "voicedex.sync.xiaomi.XiaomiSyncer"),
    SyncerEntry('cohere'           , 'Cohere', 'stt', "voicedex.sync.cohere.CohereSyncer"),
    SyncerEntry('bosonai'          , 'Boson AI', 'both', "voicedex.sync.bosonai.BosonAISyncer"),
    SyncerEntry('phonic'           , 'Phonic', 'sts', "voicedex.sync.phonic.PhonicSyncer"),
    SyncerEntry('bland'            , 'Bland', 'tts', "voicedex.sync.bland.BlandSyncer"),
    SyncerEntry('zoom'             , 'Zoom AI Services', 'stt', "voicedex.sync.zoom.ZoomSyncer"),
    SyncerEntry('modulate'         , 'Modulate', 'stt', "voicedex.sync.modulate.ModulateSyncer"),
    SyncerEntry('voicegain'        , 'Voicegain', 'stt', "voicedex.sync.voicegain.VoicegainSyncer"),
    SyncerEntry('picovoice'        , 'Picovoice', 'both', "voicedex.sync.picovoice.PicovoiceSyncer"),
    SyncerEntry('kugelaudio'       , 'KugelAudio', 'tts', "voicedex.sync.kugelaudio.KugelAudioSyncer"),
    SyncerEntry('vatis'            , 'Vatis Tech', 'stt', "voicedex.sync.vatis.VatisSyncer"),
    SyncerEntry('shunya'           , 'Shunya Labs', 'stt', "voicedex.sync.shunya.ShunyaSyncer"),
    SyncerEntry('zyphra'           , 'Zyphra', 'tts', "voicedex.sync.zyphra.ZyphraSyncer"),
    SyncerEntry('gnani'            , 'Gnani.ai', 'both', "voicedex.sync.gnani.GnaniSyncer"),
    SyncerEntry('upliftai'         , 'Uplift AI', 'both', "voicedex.sync.upliftai.UpliftAISyncer"),
    SyncerEntry('navana'           , 'Navana.ai', 'both', "voicedex.sync.navana.NavanaSyncer"),
    SyncerEntry('dubverse'           , 'Dubverse', 'tts', "voicedex.sync.retired.RetiredSyncer", retired=True),
    SyncerEntry('reverie'          , 'Reverie', 'both', "voicedex.sync.reverie.ReverieSyncer"),
    SyncerEntry('bhashini'         , 'Bhashini', 'both', "voicedex.sync.bhashini.BhashiniSyncer"),
    SyncerEntry('fptai'            , 'FPT.AI', 'both', "voicedex.sync.fptai.FptAISyncer"),
    SyncerEntry('iapp'             , 'iApp Technology', 'both', "voicedex.sync.iapp.IappSyncer"),
    SyncerEntry('botnoi'           , 'Botnoi Voice', 'tts', "voicedex.sync.botnoi.BotnoiSyncer"),
    SyncerEntry('munsit'           , 'Munsit', 'both', "voicedex.sync.munsit.MunsitSyncer"),
    SyncerEntry('spitch'           , 'Spitch', 'both', "voicedex.sync.spitch.SpitchSyncer"),
    SyncerEntry('sunbird'          , 'Sunbird AI', 'both', "voicedex.sync.sunbird.SunbirdSyncer"),
    SyncerEntry('lelapa'           , 'Lelapa AI', 'stt', "voicedex.sync.lelapa.LelapaSyncer"),
    SyncerEntry('aisha'            , 'Aisha AI', 'both', "voicedex.sync.aisha.AishaSyncer"),
    SyncerEntry('amivoice'         , 'AmiVoice', 'stt', "voicedex.sync.amivoice.AmiVoiceSyncer"),
    SyncerEntry('coefont'          , 'CoeFont', 'tts', "voicedex.sync.coefont.CoeFontSyncer"),
    SyncerEntry('rtzr'             , 'ReturnZero (RTZR)', 'stt', "voicedex.sync.rtzr.RtzrSyncer"),
    # ── Expansion wave 4: sales-led vendors with public API docs ──
    SyncerEntry('deepdub'          , 'Deepdub', 'tts', "voicedex.sync.deepdub.DeepdubSyncer"),
    SyncerEntry('intron'           , 'Intron Health', 'stt', "voicedex.sync.intron.IntronSyncer"),
    SyncerEntry('sestek'           , 'Sestek (Knovvu)', 'both', "voicedex.sync.sestek.SestekSyncer"),
    SyncerEntry('huawei-cloud'     , 'Huawei Cloud SIS', 'both', "voicedex.sync.huawei_cloud.HuaweiCloudSyncer"),
    SyncerEntry('readspeaker'      , 'ReadSpeaker', 'tts', "voicedex.sync.readspeaker.ReadSpeakerSyncer"),
    SyncerEntry('acapela'          , 'Acapela Group', 'tts', "voicedex.sync.acapela.AcapelaSyncer"),
    SyncerEntry('cereproc'         , 'CereProc', 'tts', "voicedex.sync.cereproc.CereProcSyncer"),
    SyncerEntry('phonexia'         , 'Phonexia', 'stt', "voicedex.sync.phonexia.PhonexiaSyncer"),
    SyncerEntry('verbio'             , 'Verbio', 'both', "voicedex.sync.retired.RetiredSyncer", retired=True),
    SyncerEntry('respeecher'       , 'Respeecher', 'tts', "voicedex.sync.respeecher.RespeecherSyncer"),
    SyncerEntry('khaya'            , 'Khaya AI (GhanaNLP)', 'both', "voicedex.sync.khaya.KhayaSyncer"),
    # ── 2026-11 gap pass (docs) ──
    SyncerEntry('deepl'            , 'DeepL Voice API', 'stt', "voicedex.sync.deepl.DeepLSyncer"),
    SyncerEntry('baidu'            , 'Baidu AI Cloud Speech', 'both', "voicedex.sync.baidu.BaiduSyncer"),
    SyncerEntry('liquidai'         , 'Liquid AI', 'both', "voicedex.sync.liquidai.LiquidAISyncer"),
    SyncerEntry('aispeech'         , 'AISpeech (思必驰)', 'both', "voicedex.sync.aispeech.AISpeechSyncer"),
    SyncerEntry('oracle-oci'       , 'Oracle OCI Speech', 'both', "voicedex.sync.oracle_oci.OracleOCISyncer"),
    SyncerEntry('proto'            , 'Proto', 'both', "voicedex.sync.proto.ProtoSyncer"),
    SyncerEntry('aivis'            , 'Aivis Cloud API', 'tts', "voicedex.sync.aivis.AivisSyncer"),
    SyncerEntry('reson8'           , 'Reson8', 'stt', "voicedex.sync.reson8.Reson8Syncer"),
    SyncerEntry('krutrim'          , 'Krutrim', 'both', "voicedex.sync.krutrim.KrutrimSyncer"),
    SyncerEntry('humelo'           , 'Humelo', 'tts', "voicedex.sync.humelo.HumeloSyncer"),
    SyncerEntry('aqua'             , 'Aqua Voice (Avalon)', 'stt', "voicedex.sync.aqua.AquaSyncer"),
    SyncerEntry('unisound'         , 'Unisound (云知声)', 'both', "voicedex.sync.unisound.UnisoundSyncer"),
    SyncerEntry('chimege'          , 'Chimege', 'both', "voicedex.sync.chimege.ChimegeSyncer"),
    SyncerEntry('vbee'             , 'Vbee', 'tts', "voicedex.sync.vbee.VbeeSyncer"),
    SyncerEntry('aitalk'           , 'AITalk (AI Inc.)', 'tts', "voicedex.sync.aitalk.AITalkSyncer"),
    SyncerEntry('breezeblue'       , 'BreezeBlue', 'tts', "voicedex.sync.breezeblue.BreezeBlueSyncer"),
    SyncerEntry('voiceai'          , 'Voice.ai', 'tts', "voicedex.sync.voiceai.VoiceAISyncer"),
    SyncerEntry('voxist'           , 'Voxist', 'stt', "voicedex.sync.voxist.VoxistSyncer"),
    SyncerEntry('daglo'            , 'Daglo (ActionPower)', 'stt', "voicedex.sync.daglo.DagloSyncer"),
    SyncerEntry('skt'              , 'SK Telecom (A.X)', 'tts', "voicedex.sync.skt.SKTSyncer"),
    SyncerEntry('tbank'            , 'T-Bank VoiceKit', 'both', "voicedex.sync.tbank.TBankSyncer"),
    SyncerEntry('sarj'             , 'Sarj.ai', 'both', "voicedex.sync.sarj.SarjSyncer"),
    SyncerEntry('aiforthai'        , 'AI for Thai (NECTEC)', 'both', "voicedex.sync.aiforthai.AIForThaiSyncer"),
    # ── Open-weights publishers (Hugging Face Hub API; voicedex/sync/open_weights.py) ──
    SyncerEntry("hexgrad",           "Hexgrad",           "tts",  "voicedex.sync.open_weights.HexgradSyncer"),
    SyncerEntry("kyutai",            "Kyutai",            "both", "voicedex.sync.open_weights.KyutaiSyncer"),
    SyncerEntry("openbmb",           "OpenBMB",           "tts",  "voicedex.sync.open_weights.OpenBMBSyncer"),
    SyncerEntry("k2-fsa",            "k2-fsa (Next-gen Kaldi)", "tts", "voicedex.sync.open_weights.K2FsaSyncer"),
    SyncerEntry("ai4bharat",         "AI4Bharat",         "both", "voicedex.sync.open_weights.AI4BharatSyncer"),
    SyncerEntry("canopylabs",        "Canopy Labs",       "tts",  "voicedex.sync.open_weights.CanopyLabsSyncer"),
    SyncerEntry("sesame",            "Sesame",            "tts",  "voicedex.sync.open_weights.SesameSyncer"),
    SyncerEntry("microsoft",         "Microsoft (open weights)", "both", "voicedex.sync.open_weights.MicrosoftSyncer"),
    SyncerEntry("swivid",            "SWivid (F5-TTS)",   "tts",  "voicedex.sync.open_weights.SWividSyncer"),
    SyncerEntry("funaudiollm",       "FunAudioLLM (Alibaba Tongyi)", "both", "voicedex.sync.open_weights.FunAudioLLMSyncer"),
    SyncerEntry('openmoss'          , 'OpenMOSS (Fudan)', 'tts', "voicedex.sync.open_weights.OpenMOSSSyncer"),
    SyncerEntry('kittenml'          , 'KittenML', 'tts', "voicedex.sync.open_weights.KittenMLSyncer"),
    SyncerEntry('nari-labs'         , 'Nari Labs', 'tts', "voicedex.sync.open_weights.NariLabsSyncer"),
    SyncerEntry('myshell-ai'        , 'MyShell', 'tts', "voicedex.sync.open_weights.MyShellSyncer"),
    SyncerEntry('index-tts'         , 'IndexTTS (bilibili)', 'tts', "voicedex.sync.open_weights.IndexTTSSyncer"),
    SyncerEntry('rvc-boss'          , 'RVC-Boss (GPT-SoVITS)', 'tts', "voicedex.sync.open_weights.RVCBossSyncer"),
    SyncerEntry('suno'              , 'Suno (Bark)', 'tts', "voicedex.sync.open_weights.SunoSyncer"),
    SyncerEntry('parler-tts'        , 'Parler-TTS (Hugging Face)', 'tts', "voicedex.sync.open_weights.ParlerTTSSyncer"),
    SyncerEntry('maya-research'     , 'Maya Research', 'tts', "voicedex.sync.open_weights.MayaResearchSyncer"),
    SyncerEntry('2noise'             , '2Noise (ChatTTS)', 'tts', "voicedex.sync.open_weights.TwoNoiseSyncer"),
    # Retired, never synced — catalogued so "is X still alive?" has an answer.
    SyncerEntry("playht",            "PlayHT",            "tts",  "voicedex.sync.retired.RetiredSyncer", retired=True),
    SyncerEntry("coqui",             "Coqui",             "tts",  "voicedex.sync.retired.RetiredSyncer", retired=True, open_weights_path="voicedex.sync.open_weights.CoquiOpenSyncer"),
    SyncerEntry('sber-salutespeech', 'Sber SaluteSpeech', 'both', "voicedex.sync.retired.RetiredSyncer", retired=True, open_weights_path="voicedex.sync.open_weights.SberOpenSyncer"),
    SyncerEntry('nijivoice'        , 'Nijivoice', 'tts', "voicedex.sync.retired.RetiredSyncer", retired=True),
    SyncerEntry('replica'          , 'Replica Studios', 'tts', "voicedex.sync.retired.RetiredSyncer", retired=True),
    SyncerEntry('symbl'            , 'Symbl.ai', 'stt', "voicedex.sync.retired.RetiredSyncer", retired=True),
    SyncerEntry("supertone",         "Supertone",         "tts",  "voicedex.sync.retired.RetiredSyncer", retired=True, open_weights_path="voicedex.sync.open_weights.SupertoneOpenSyncer"),
]

BY_ID: dict[str, SyncerEntry] = {e.provider_id: e for e in REGISTRY}


def get_syncer_entry(provider_id: str) -> SyncerEntry | None:
    return BY_ID.get(provider_id)


def load_syncer(provider_id: str) -> ProviderSyncer:
    """Import and instantiate the syncer for `provider_id`. Raises KeyError if unknown."""
    entry = BY_ID[provider_id]
    path = entry.open_weights_path if entry.retired and entry.open_weights_path else entry.syncer_path
    module_path, class_name = path.rsplit(".", 1)
    cls = getattr(importlib.import_module(module_path), class_name)
    return cls()
