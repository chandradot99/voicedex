"""
Azure Speech sync script.

Source: api (subscription key; F0 free tier is enough)
  - TTS voices : GET https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list
  - TTS models : derived from voice names. Azure has no `model` parameter — a voice's ShortName
                 suffix selects the model family: "en-US-AvaNeural" → Neural,
                 "en-US-AvaMultilingualNeural" → MultilingualNeural,
                 "en-US-Ava:DragonHDLatestNeural" → DragonHDLatestNeural,
                 "cs-CZ-Grant:MAI-Voice-2.1-Flash" → MAI-Voice-2.1-Flash. The suffix is the model id,
                 so a consumer can map any voice name to its model without a lookup table.
  - STT models : GET https://{region}.api.cognitive.microsoft.com/speechtotext/v3.2/models/base
                 (paginated). Azure STT has no user-selected model for normal recognition — it picks
                 the latest base model per locale — so we publish the two modes (real-time, batch)
                 with their exact live locale lists, plus named model families (e.g. Whisper) the
                 base-model list exposes, with their transcription deprecation date as eol_date.

Docs supplement: STT models selected by name outside the base-model list (e.g. MAI-Transcribe) and the
speech-to-speech Voice Live API come from the docs (provenance docs). API records win on id collisions.

Voices with Status "Deprecated" are skipped; "Preview" voices are kept (meta.status), and a family
whose voices are all Preview is lifecycle "beta".
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from datetime import datetime, timezone

import httpx

from voicedex.config import settings
from voicedex.sync.ai_parser import parse_models_from_docs
from voicedex.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncModel, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.language import ACCENT_MAP, normalize_languages

_VOICES_URL = "https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list"
_STT_MODELS_URL = "https://{region}.api.cognitive.microsoft.com/speechtotext/v3.2/models/base"
_MAX_STT_PAGES = 50

_STT_DOCS_URLS = [
    "https://learn.microsoft.com/en-us/azure/ai-services/speech-service/mai-transcribe",
    "https://learn.microsoft.com/en-us/azure/ai-services/speech-service/release-notes",
    "https://azure.microsoft.com/en-us/pricing/details/speech/",
]
_STT_DOCS_GUIDANCE = (
    "Return ONLY speech-to-text models a developer selects by name that are NOT ordinary per-locale base "
    "models (e.g. Microsoft AI transcription models). Exact model identifiers as used in the API/SDK, "
    "languages, lifecycle (preview → beta), per-hour or per-minute pricing as published."
)
_STS_DOCS_URLS = [
    "https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live",
    "https://learn.microsoft.com/en-us/azure/ai-services/speech-service/voice-live-language-support",
    "https://azure.microsoft.com/en-us/pricing/details/speech/",
]
_STS_DOCS_GUIDANCE = (
    "Return the Voice Live API speech-to-speech offerings as models: one per billing tier / selectable "
    "model as documented (exact ids or tier names used in the API). Languages, interfaces, per-token or "
    "per-minute pricing as published (unit token with variants for audio in/out)."
)

# Recommended default family, best first. Only used if present in the live voice list.
_TTS_DEFAULT_PREFERENCE = ["DragonHDLatestNeural", "MultilingualNeural", "Neural"]
_NO_COLON_SUFFIXES = ("TurboMultilingualNeural", "MultilingualNeural", "Neural")

_GENDER = {"male": "male", "female": "female", "neutral": "neutral"}


class AzureSyncer(ProviderSyncer):
    provider_id = "azure"
    source = "mixed"

    async def sync(self) -> SyncResult:
        if not settings.azure_speech_key:
            raise ValueError("AZURE_SPEECH_KEY is not set in .env")
        region = settings.azure_speech_region or "eastus"
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            voices_data = await self._fetch_voices(client, region)
            base_models = await self._fetch_stt_base_models(client, region)

        voices_data = [v for v in voices_data if v.get("Status") != "Deprecated"]
        (docs_stt, _), (sts_models, _) = await asyncio.gather(
            parse_models_from_docs(seed_urls=_STT_DOCS_URLS, provider_id=self.provider_id,
                                   model_type="stt", guidance=_STT_DOCS_GUIDANCE),
            parse_models_from_docs(seed_urls=_STS_DOCS_URLS, provider_id=self.provider_id,
                                   model_type="sts", guidance=_STS_DOCS_GUIDANCE),
        )
        stt_models = _stt_models(base_models)
        api_ids = {m.model_id for m in stt_models}
        stt_models += [m for m in docs_stt if m.model_id not in api_ids]
        return SyncResult(
            stt_models=stt_models,
            tts_models=_tts_models(voices_data),
            tts_voices=[_to_voice(v) for v in voices_data],
            sts_models=sts_models,
            source=self.source,
            api_urls=[_VOICES_URL, _STT_MODELS_URL],
            docs_urls=list(dict.fromkeys(_STT_DOCS_URLS + _STS_DOCS_URLS)),
            notes=f"{len(voices_data)} voices; {len(base_models)} STT base models.",
        )

    # ── Fetch ─────────────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {"Ocp-Apim-Subscription-Key": settings.azure_speech_key}

    async def _fetch_voices(self, client: httpx.AsyncClient, region: str) -> list[dict]:
        resp = await get_with_retry(client, _VOICES_URL.format(region=region), headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def _fetch_stt_base_models(self, client: httpx.AsyncClient, region: str) -> list[dict]:
        url: str | None = _STT_MODELS_URL.format(region=region) + "?top=100"
        out: list[dict] = []
        for _ in range(_MAX_STT_PAGES):
            resp = await get_with_retry(client, url, headers=self._headers())
            resp.raise_for_status()
            body = resp.json()
            out += body.get("values", [])
            url = body.get("@nextLink")
            if not url:
                return out
        raise RuntimeError(f"Azure STT base-model pagination exceeded {_MAX_STT_PAGES} pages")


# ── TTS ───────────────────────────────────────────────────────────────────────

def voice_family(short_name: str) -> str:
    """ShortName → model family id (the suffix that selects the model)."""
    if ":" in short_name:
        return short_name.split(":", 1)[1]
    for suffix in _NO_COLON_SUFFIXES:
        if short_name.endswith(suffix):
            return suffix
    return "Neural"


def _voice_languages(v: dict) -> list[str]:
    locales = [v.get("Locale") or ""] + list(v.get("SecondaryLocaleList") or [])
    return list(dict.fromkeys(normalize_languages([loc for loc in locales if loc])))


def _tts_models(voices: list[dict]) -> list[SyncModel]:
    families: dict[str, list[dict]] = defaultdict(list)
    for v in voices:
        families[voice_family(v["ShortName"])].append(v)

    default = next((f for f in _TTS_DEFAULT_PREFERENCE if f in families), None)
    models = []
    for family, vs in families.items():
        tags = defaultdict(set)
        for v in vs:
            for k, vals in (v.get("VoiceTag") or {}).items():
                if k in ("ModelSeries", "Source", "Capabilities"):
                    tags[k].update(vals)
        all_preview = all(v.get("Status") == "Preview" for v in vs)
        caps = ["ssml"]  # Azure synthesis is SSML-driven for every voice
        if any(v.get("StyleList") for v in vs):
            caps.append("style_control")
        rates = sorted({int(v["SampleRateHertz"]) for v in vs if str(v.get("SampleRateHertz", "")).isdigit()})
        models.append(SyncModel(
            model_id=family,
            display_name=_family_display(family),
            type="tts",
            languages=sorted({lang for v in vs for lang in _voice_languages(v)}),
            streaming=True,
            is_default=family == default,
            lifecycle="beta" if all_preview else "ga",
            sample_rates_hz=rates,
            capabilities=caps,
            interfaces=["http", "websocket"],
            meta={k: v for k, v in {
                "voice_type": sorted({v.get("VoiceType") for v in vs if v.get("VoiceType")}),
                "model_series": sorted(tags["ModelSeries"]),
                "source": sorted(tags["Source"]),
                "voice_capabilities": sorted(tags["Capabilities"]),
                "voice_count": len(vs),
            }.items() if v},
        ))
    return models


def _family_display(family: str) -> str:
    if family.startswith("MAI-"):
        return family.replace("-", " ").replace("MAI Voice", "MAI-Voice")
    words = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=HD)(?=[A-Z])", " ", family)
    return f"Azure {words}"


def _to_voice(v: dict) -> SyncVoice:
    tag = v.get("VoiceTag") or {}
    languages = _voice_languages(v)
    persona = (tag.get("PersonaId") or [None])[0]
    family = voice_family(v["ShortName"])
    display = persona or re.sub(r"\s*(Multilingual|Turbo|Dragon|MAI-Voice).*$", "", v.get("DisplayName") or "") \
        or v["ShortName"]
    caps = ["multilingual_native"] if "multi-lingual" in (tag.get("Capabilities") or []) else []
    return SyncVoice(
        voice_id=v["ShortName"],
        display_name=display,
        gender=_GENDER.get((v.get("Gender") or "").lower()),
        category="premade",
        languages=languages,
        accent=_accent_from_locale(v.get("Locale") or ""),
        compatible_models=[family],
        capabilities=caps,
        use_cases=list(tag.get("TailoredScenarios") or []),
        tags=list(tag.get("VoicePersonalities") or []),
        meta={k: val for k, val in {
            "status": v.get("Status"),
            "local_name": v.get("LocalName") if v.get("LocalName") != v.get("DisplayName") else None,
            "locale_name": v.get("LocaleName"),
            "styles": v.get("StyleList") or None,
            "roles": v.get("RolePlayList") or None,
            "words_per_minute": int(v["WordsPerMinute"]) if str(v.get("WordsPerMinute", "")).isdigit() else None,
            "sample_rate_hz": int(v["SampleRateHertz"]) if str(v.get("SampleRateHertz", "")).isdigit() else None,
            "voice_capabilities": tag.get("Capabilities") or None,
        }.items() if val},
    )


def _accent_from_locale(locale: str) -> str | None:
    parts = locale.split("-")
    if len(parts) >= 3 and len(parts[1]) == 4:  # script subtag, e.g. zh-Hans-CN
        return ACCENT_MAP.get(parts[2].upper())
    return ACCENT_MAP.get(parts[1].upper()) if len(parts) >= 2 else None


# ── STT ───────────────────────────────────────────────────────────────────────

def _live(m: dict, now: datetime) -> bool:
    raw = ((m.get("properties") or {}).get("deprecationDates") or {}).get("transcriptionDateTime")
    if not raw:
        return True
    return datetime.fromisoformat(raw.replace("Z", "+00:00")) > now


def _eol(m: dict) -> str | None:
    raw = ((m.get("properties") or {}).get("deprecationDates") or {}).get("transcriptionDateTime")
    return raw[:10] if raw else None


def _stt_models(base_models: list[dict]) -> list[SyncModel]:
    now = datetime.now(timezone.utc)
    live = [m for m in base_models if _live(m, now)]
    if not live:
        raise RuntimeError("Azure returned no live STT base models — refusing to continue")
    feats = lambda m: (m.get("properties") or {}).get("features") or {}  # noqa: E731
    realtime = sorted(set(normalize_languages([m["locale"] for m in live if feats(m).get("supportsEndpoints")])))
    batch = sorted(set(normalize_languages([m["locale"] for m in live if feats(m).get("supportsTranscriptions")])))
    adaptable = any(feats(m).get("supportsAdaptationsWith") for m in live)
    common_caps = ["punctuation", "profanity_filter"] + (["custom_vocabulary"] if adaptable else [])

    models = [
        SyncModel(
            model_id="azure-stt-realtime", display_name="Azure Speech-to-Text (real-time)", type="stt",
            languages=realtime, streaming=True, is_default=True, capabilities=common_caps,
            interfaces=["websocket"],
            description="Real-time recognition; Azure selects the latest base model for the locale.",
            meta={"mode": "realtime", "batch": False},
        ),
        SyncModel(
            model_id="azure-stt-batch", display_name="Azure Speech-to-Text (batch)", type="stt",
            languages=batch, streaming=False, capabilities=common_caps, interfaces=["http"],
            description="Batch transcription of stored audio; latest base model per locale.",
            meta={"mode": "batch", "batch": True},
        ),
    ]

    # Named model families selectable by base-model id (e.g. Whisper), one entry per family.
    named: dict[str, list[dict]] = defaultdict(list)
    for m in live:
        match = re.search(r"Whisper[\w .-]*", m.get("displayName") or "")
        if match:
            named[match.group(0).strip()].append(m)
    for name, ms in named.items():
        models.append(SyncModel(
            model_id=re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
            display_name=f"Azure {name}",
            type="stt",
            languages=sorted(set(normalize_languages([m["locale"] for m in ms]))),
            streaming=False,
            interfaces=["http"],
            eol_date=min(filter(None, (_eol(m) for m in ms)), default=None),
            description=f"{name} hosted by Azure; selected by base-model id in batch transcription.",
            meta={"batch": True, "base_model_ids": sorted(m["self"].rsplit("/", 1)[-1] for m in ms)},
        ))
    return models


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    result = await AzureSyncer().sync()
    for kind, ms in (("STT", result.stt_models), ("TTS", result.tts_models)):
        print(f"\n=== {kind} Models ({len(ms)}) ===")
        for m in ms:
            print(f"  {m.model_id!r:32} {m.lifecycle:5} langs={len(m.languages):3} default={m.is_default}")
    print(f"\n{len(result.tts_voices)} voices. {result.notes}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_main())
