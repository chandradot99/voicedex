"""
Soniox sync script.

Source: mixed (API-first)
  - STT models : GET https://api.soniox.com/v1/models       (languages, mode, translation per model)
  - TTS models : GET https://api.soniox.com/v1/tts-models   (languages, voice cloning, speed range)
  - TTS voices : GET https://api.soniox.com/v1/shared-voices?model=<id>  (built-in voices only;
                 a user's cloned voices live at /v1/voices and are never read)
  - Removal dates: parsed from the docs model pages ("Will be removed <Mon D, YYYY>") — the API
                 doesn't expose them. Best-effort: a docs fetch failure just means no eol_date.

Aliases (aliased_model_id != null, e.g. stt-rt-v4 → stt-rt-v5) are not separate records; they're
listed in the target's meta.aliases.

Auth: Authorization: Bearer <SONIOX_API_KEY>
"""

from __future__ import annotations

import asyncio
import re
from datetime import date, datetime

import httpx

from voicedex.config import settings
from voicedex.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncModel, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.language import normalize_languages

_API = "https://api.soniox.com/v1"
_DOCS_STT_MODELS = "https://docs.soniox.com/stt/models.mdx"
_DOCS_TTS_MODELS = "https://docs.soniox.com/tts/models.mdx"
_DOCS_URLS = [
    _DOCS_STT_MODELS, _DOCS_TTS_MODELS,
    "https://docs.soniox.com/stt/concepts/speaker-diarization.mdx",
    "https://docs.soniox.com/stt/concepts/language-identification.mdx",
    "https://docs.soniox.com/stt/concepts/timestamps.mdx",
    "https://docs.soniox.com/stt/concepts/context.mdx",
]

# Documented for every current STT model (docs.soniox.com/stt/concepts/*): speaker diarization,
# language identification, word-level timestamps, custom context. Translation comes from the API.
_STT_BASE_CAPS = ["custom_vocabulary", "language_detection", "punctuation", "speaker_diarization",
                  "word_timestamps"]

_REMOVAL_RE = re.compile(r"\*\*([a-z0-9-]+)\*\*[^\n]*?Will be removed ([A-Z][a-z]{2,8} \d{1,2}, \d{4})")


class SonioxSyncer(ProviderSyncer):
    provider_id = "soniox"
    source = "mixed"

    async def sync(self) -> SyncResult:
        if not settings.soniox_api_key:
            raise ValueError("SONIOX_API_KEY is not set in .env")
        headers = {"Authorization": f"Bearer {settings.soniox_api_key}"}
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=headers) as client:
            stt_raw, tts_raw, removals = await asyncio.gather(
                _get_json(client, f"{_API}/models"),
                _get_json(client, f"{_API}/tts-models"),
                _fetch_removals(client),
            )
            stt_models = parse_stt_models(stt_raw.get("models") or [], removals)
            tts_list = tts_raw.get("models") or []
            tts_models = parse_tts_models(tts_list, removals)
            voices_by_model = {
                m.model_id: await _fetch_shared_voices(client, m.model_id) for m in tts_models
            }
        tts_voices = parse_voices(voices_by_model, {m.model_id: m.languages for m in tts_models})

        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            api_urls=[f"{_API}/models", f"{_API}/tts-models", f"{_API}/shared-voices"],
            docs_urls=_DOCS_URLS,
            notes=f"{len(stt_models)} STT, {len(tts_models)} TTS models, {len(tts_voices)} shared voices.",
        )


# ── Parsing (pure; tested with recorded payloads) ─────────────────────────────

def _aliases(models: list[dict]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for m in models:
        if m.get("aliased_model_id"):
            out.setdefault(m["aliased_model_id"], []).append(m["id"])
    return {k: sorted(v) for k, v in out.items()}


def _version(model_id: str) -> int:
    m = re.search(r"-v(\d+)", model_id)
    return int(m.group(1)) if m else -1


def _langs(raw: list) -> list[str]:
    return normalize_languages([x["code"] if isinstance(x, dict) else x for x in raw or []])


def _eol(model_id: str, removals: dict[str, str]) -> str | None:
    d = removals.get(model_id)
    return d if d and d > date.today().isoformat() else None


def parse_stt_models(models: list[dict], removals: dict[str, str]) -> list[SyncModel]:
    aliases = _aliases(models)
    real = [m for m in models if m.get("id") and not m.get("aliased_model_id")]
    live = [m for m in real if not _eol(m["id"], removals)]
    rt = [m for m in live if m.get("transcription_mode") == "real_time"] or live
    default = max(rt, key=lambda m: _version(m["id"]))["id"] if rt else None

    out = []
    for m in real:
        realtime = m.get("transcription_mode") == "real_time"
        caps = list(_STT_BASE_CAPS)
        if m.get("one_way_translation") or m.get("translation_targets") or m.get("two_way_translation"):
            caps.append("translation")
        meta: dict = {"transcription_mode": m.get("transcription_mode"),
                      "parent_model_id": f"stt-{'rt' if realtime else 'async'}"}
        if not realtime:
            meta["batch"] = True
        if aliases.get(m["id"]):
            meta["aliases"] = aliases[m["id"]]
        for k in ("one_way_translation", "two_way_translation"):
            if m.get(k):
                meta[k] = m[k]
        if m.get("supports_agent_text_input"):
            meta["agent_text_input"] = True
        eol = _eol(m["id"], removals)
        if eol:
            newer = [x["id"] for x in live if x.get("transcription_mode") == m.get("transcription_mode")]
            if newer:
                meta["replacement"] = max(newer, key=_version)
        out.append(SyncModel(
            model_id=m["id"],
            display_name=m.get("name") or m["id"],
            type="stt",
            languages=_langs(m.get("languages")),
            streaming=realtime,
            is_default=m["id"] == default,
            eol_date=eol,
            capabilities=sorted(caps),
            interfaces=["websocket"] if realtime else ["http"],
            meta=meta,
        ))
    return out


def parse_tts_models(models: list[dict], removals: dict[str, str]) -> list[SyncModel]:
    aliases = _aliases(models)
    real = [m for m in models if m.get("id") and not m.get("aliased_model_id")]
    live = [m for m in real if not _eol(m["id"], removals)]
    default = max(live, key=lambda m: _version(m["id"]))["id"] if live else None
    out = []
    for m in real:
        caps = []
        if m.get("supports_voice_cloning"):
            caps.append("voice_cloning")
        if m.get("supports_speed_adjustment"):
            caps.append("prosody_control")
        meta: dict = {}
        if aliases.get(m["id"]):
            meta["aliases"] = aliases[m["id"]]
        if m.get("supports_speed_adjustment"):
            meta["speed_range"] = [m.get("speed_min"), m.get("speed_max")]
        for k in ("supports_timestamps", "supports_silence_reduction", "voice_cloning_max_audio_duration_ms"):
            if m.get(k):
                meta[k.removeprefix("supports_")] = m[k]
        out.append(SyncModel(
            model_id=m["id"],
            display_name=m.get("name") or m["id"],
            type="tts",
            languages=_langs(m.get("languages")),
            streaming=True,
            is_default=m["id"] == default,
            eol_date=_eol(m["id"], removals),
            capabilities=sorted(caps),
            meta=meta,
        ))
    return out


def parse_voices(voices_by_model: dict[str, list[dict]], model_langs: dict[str, list[str]]) -> list[SyncVoice]:
    merged: dict[str, dict] = {}
    compat: dict[str, set[str]] = {}
    for model_id, voices in voices_by_model.items():
        for v in voices:
            if v.get("id"):
                merged.setdefault(v["id"], v)
                compat.setdefault(v["id"], set()).add(model_id)
    out = []
    for vid, v in merged.items():
        models = sorted(compat[vid])
        out.append(SyncVoice(
            voice_id=vid,
            display_name=vid,
            gender=v.get("gender") if v.get("gender") in ("male", "female", "neutral") else None,
            category="premade",
            # Shared voices speak every language of their model (language mixing per utterance).
            languages=sorted({lang for mid in models for lang in model_langs.get(mid, [])}),
            description=v.get("description"),
            accent=v.get("accent"),
            age=(v.get("age") or "").replace("_", " ") or None,
            use_cases=[u.replace("_", " ") for u in v.get("use_case") or []],
            tags=list(v.get("style") or []),
            compatible_models=models,
        ))
    return out


def parse_removals(markdown: str) -> dict[str, str]:
    out = {}
    for model_id, when in _REMOVAL_RE.findall(markdown):
        try:
            out[model_id] = datetime.strptime(when.replace("Sept", "Sep"), "%b %d, %Y").date().isoformat()
        except ValueError:
            try:
                out[model_id] = datetime.strptime(when, "%B %d, %Y").date().isoformat()
            except ValueError:
                continue
    return out


# ── HTTP ──────────────────────────────────────────────────────────────────────

async def _get_json(client: httpx.AsyncClient, url: str, **params) -> dict:
    resp = await get_with_retry(client, url, params=params or None)
    resp.raise_for_status()
    return resp.json()


async def _fetch_shared_voices(client: httpx.AsyncClient, model_id: str) -> list[dict]:
    voices, cursor = [], None
    for _ in range(100):
        params = {"model": model_id, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        page = await _get_json(client, f"{_API}/shared-voices", **params)
        voices += page.get("voices") or []
        cursor = page.get("next_page_cursor")
        if not cursor:
            break
    return voices


async def _fetch_removals(client: httpx.AsyncClient) -> dict[str, str]:
    out: dict[str, str] = {}
    for url in (_DOCS_STT_MODELS, _DOCS_TTS_MODELS):
        try:
            resp = await client.get(url, headers={"Authorization": ""})
            if resp.status_code == 200:
                out.update(parse_removals(resp.text))
        except httpx.HTTPError:
            pass
    return out
