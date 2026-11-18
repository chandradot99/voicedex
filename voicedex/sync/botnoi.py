"""
Botnoi Voice (Botnoi Group, Thailand) — text-to-speech in three voice generations: V1 Classic, V2 Premium, V4 Beta.

Source: mixed. Models come from the docs (https://voice.botnoi.ai/llms.txt — the short API guide, which
https://voice.botnoi.ai/llm.txt defers to). Voices come from Botnoi's public, keyless speaker-list endpoints
(GET /openapi/v1/get_speaker_data, get_speaker_data_v2, get_speaker_data_v4). Each generation has its own speaker-id
namespace (V1 "2" is Bow, V2/V4 "2" is Ava), so the catalog voice_id is "<version>-<speaker_id>" and the raw API
`speaker` value is kept in meta.speaker_id. V4 lists only preset voices (community clones are skipped) and carries no
language or gender data. Prices are in points (bought in THB packs), not money per unit, so they go in meta.
"""

from __future__ import annotations

import httpx

from voicedex.sync.base import HTTP_TIMEOUT, SyncModel, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.docs_only import DocsOnlySyncer
from voicedex.sync.language import normalize_languages

API = "https://api-voice.botnoi.ai/openapi/v1"
SPEAKER_LISTS = {
    "v1": f"{API}/get_speaker_data",
    "v2": f"{API}/get_speaker_data_v2",
    "v4": f"{API}/get_speaker_data_v4",
}
# Botnoi's own codes that are not BCP-47: "sg" is Singapore English (the IMDA Singapore voices), not Sango.
_LANG_FIX = {"sg": "en-SG"}
_GENDERS = {"female": "female", "male": "male"}


def _langs(codes: list[str]) -> list[str]:
    return normalize_languages([_LANG_FIX.get(c.lower(), c) for c in codes if c])


def _title(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.replace("_", "-").split("-") if w)


def parse_v1_v2(version: str, rows: list[dict]) -> list[SyncVoice]:
    """V1 / V2 speaker lists: a JSON array of speakers with names, gender, age, styles and languages."""
    voices = []
    for r in rows:
        sid = str(r.get("speaker_id") or "").strip()
        if not sid:
            continue
        styles = list(dict.fromkeys((r.get("eng_voice_style") or []) + (r.get("eng_speech_style") or [])))
        meta = {
            "speaker_id": sid,
            "api_version": version,
            "thai_name": r.get("thai_name"),
            "primary_language": r.get("language"),
            "botnoi_languages": r.get("available_language") or [],
            "price_multiplier": r.get("price"),
            "speed": r.get("eng_speed"),
        }
        voices.append(SyncVoice(
            voice_id=f"{version}-{sid}",
            display_name=(r.get("eng_name") or r.get("thai_name") or sid).strip(),
            gender=_GENDERS.get((r.get("eng_gender") or "").strip().lower()),
            category="premade",
            languages=_langs(r.get("available_language") or []),
            preview_url=r.get("audio") or None,
            age=(r.get("eng_age_style") or "").strip().lower() or None,
            tags=[s.strip().lower() for s in styles if s and s.strip()],
            compatible_models=[version],
            meta={k: v for k, v in meta.items() if v not in (None, "", [])},
        ))
    return voices


def parse_v4(payload: dict) -> list[SyncVoice]:
    """V4 speaker list: {"data": {"data": [...voices...], "presets": [...]}}; keep ready preset voices only."""
    inner = payload.get("data") or {}
    rows = inner.get("data") if isinstance(inner, dict) else inner
    voices = []
    for r in rows or []:
        sid = str(r.get("voice_id") or r.get("id") or "").strip()
        if not sid or not r.get("preset") or r.get("status") not in (None, "ready"):
            continue
        name = (r.get("name") or sid).strip()
        voices.append(SyncVoice(
            voice_id=f"v4-{sid}",
            display_name=_title(name) or sid,
            category="premade",
            preview_url=r.get("audio") or None,
            compatible_models=["v4"],
            meta={"speaker_id": sid, "api_version": "v4", "slug": name},
        ))
    return voices


class BotnoiSyncer(DocsOnlySyncer):
    provider_id = "botnoi"
    source = "mixed"
    tts_docs = [
        "https://voice.botnoi.ai/llms.txt",
        "https://voice.botnoi.ai/llm.txt",
    ]
    tts_guidance = (
        "One model per text-to-speech voice generation with its own generate_audio endpoint (model_id = the "
        "version string the estimate API uses). Lifecycle beta only where Botnoi labels the generation Beta. "
        "Prices are in points: record the API point rates in meta, never as money."
    )

    async def sync(self) -> SyncResult:
        result = await super().sync()
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            raw = {}
            for version, url in SPEAKER_LISTS.items():
                resp = await get_with_retry(client, url)
                resp.raise_for_status()
                raw[version] = resp.json()
        voices = parse_v1_v2("v1", raw["v1"]) + parse_v1_v2("v2", raw["v2"]) + parse_v4(raw["v4"])
        _fill_model_languages(result.tts_models, voices)
        result.tts_voices = voices
        result.source = self.source
        result.api_urls = list(SPEAKER_LISTS.values())
        result.notes = f"docs: {len(result.tts_models)} TTS models; api: {len(voices)} voices."
        return result


def _fill_model_languages(models: list[SyncModel], voices: list[SyncVoice]) -> None:
    """A generation's languages = the union of its voices' languages (only where the docs gave none)."""
    for m in models:
        if m.languages:
            continue
        langs = {lang for v in voices if m.model_id in v.compatible_models for lang in v.languages}
        m.languages = sorted(langs)
