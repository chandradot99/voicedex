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


REGISTRY: list[SyncerEntry] = [
    SyncerEntry("deepgram",          "Deepgram",          "both", "voicedex.sync.deepgram.DeepgramSyncer"),
    SyncerEntry("cartesia",          "Cartesia",          "both", "voicedex.sync.cartesia.CartesiaSyncer"),
    SyncerEntry("elevenlabs",        "ElevenLabs",        "both", "voicedex.sync.elevenlabs.ElevenLabsSyncer"),
    SyncerEntry("openai",            "OpenAI",            "both", "voicedex.sync.openai.OpenAISyncer"),
    SyncerEntry("google-cloud",      "Google Cloud",      "both", "voicedex.sync.google_cloud.GoogleCloudSyncer"),
    SyncerEntry("sarvam",            "Sarvam",            "both", "voicedex.sync.sarvam.SarvamSyncer"),
    SyncerEntry("azure",             "Azure Speech",      "both", "voicedex.sync.azure.AzureSyncer"),
    SyncerEntry("amazon-polly",      "Amazon Polly",      "tts",  "voicedex.sync.amazon_polly.AmazonPollySyncer"),
    SyncerEntry("humeai",            "Hume AI",           "tts",  "voicedex.sync.humeai.HumeAISyncer", retired=True),
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
    SyncerEntry("resemble",          "Resemble AI",       "tts",  "voicedex.sync.resemble.ResembleSyncer", retired=True),
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
    # Retired, never synced — catalogued so "is X still alive?" has an answer.
    SyncerEntry("playht",            "PlayHT",            "tts",  "voicedex.sync.retired.RetiredSyncer", retired=True),
    SyncerEntry("coqui",             "Coqui",             "tts",  "voicedex.sync.retired.RetiredSyncer", retired=True),
    SyncerEntry("supertone",         "Supertone",         "tts",  "voicedex.sync.retired.RetiredSyncer", retired=True),
]

BY_ID: dict[str, SyncerEntry] = {e.provider_id: e for e in REGISTRY}


def get_syncer_entry(provider_id: str) -> SyncerEntry | None:
    return BY_ID.get(provider_id)


def load_syncer(provider_id: str) -> ProviderSyncer:
    """Import and instantiate the syncer for `provider_id`. Raises KeyError if unknown."""
    entry = BY_ID[provider_id]
    module_path, class_name = entry.syncer_path.rsplit(".", 1)
    cls = getattr(importlib.import_module(module_path), class_name)
    return cls()
