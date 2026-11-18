"""
CereProc (Edinburgh; owned by Capacity since 2024) — CereVoice Cloud v2 text-to-speech REST API.

Source: mixed. The model comes from the CereVoice Cloud API docs (https://api.cerevoice.com/v2/ and its OpenAPI
file /v2/static/doc_file.json: /speak parameters, SSML support, credits) and the credit price from CereProc's
store (app.cereproc.com/cloud-credits/one-million). cereproc.com itself now redirects to capacity.com; the
product pages live on app.cereproc.com. /speak has no model parameter (a request names a voice), so the catalog
carries one model for the service. Voices come from the public, keyless GET /v2/voices list. Each speaker is
listed twice: "<Name>" and "<Name>-CereWave" (CereProc's CereWave AI neural voice); both are kept as separate
voice ids with the engine in meta.
"""

from __future__ import annotations

import httpx

from voicedex.sync.base import HTTP_TIMEOUT, SyncModel, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.docs_only import DocsOnlySyncer
from voicedex.sync.language import normalize_languages

_API = "https://api.cerevoice.com/v2/"
VOICE_LIST = _API + "voices"
_GENDERS = {"female": "female", "male": "male"}
_CEREWAVE = "-CereWave"
# Norwegian voices carry the written standard in accent_code.
_NORWEGIAN = {"nb": "nb", "nn": "nn"}


def _languages(r: dict) -> list[str]:
    lang = (r.get("language_iso") or "").strip().lower()
    if not lang:
        return []
    if lang == "no":
        lang = _NORWEGIAN.get((r.get("accent_code") or "").strip().lower(), lang)
    country = (r.get("country_iso") or "").strip()
    return normalize_languages([f"{lang}-{country}" if country else lang])


def parse_voices(payload: dict) -> list[SyncVoice]:
    """GET /v2/voices → one voice per name (the exact `voice` value for /speak)."""
    voices = []
    for r in payload.get("voices") or []:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        accent = (r.get("accent") or "").strip()
        rate = r.get("sample_rate")
        meta = {
            "engine": "CereWave AI" if name.endswith(_CEREWAVE) else None,
            "accent_code": r.get("accent_code"),
            "region": r.get("region"),
            "country": r.get("country"),
            "language_ms": r.get("language_ms"),
            "encoding": r.get("encoding"),
            "sample_rate_hz": rate,
            # Raw "genres" mix speaking styles (calm, stressed) with internal labels (kth, cereproc_video).
            "genres": [t.strip() for t in (r.get("genres") or "").split(",") if t.strip()],
        }
        voices.append(SyncVoice(
            voice_id=name,
            display_name=name,
            gender=_GENDERS.get((r.get("gender") or "").strip().lower()),
            category="premade",
            languages=_languages(r),
            # Some rows repeat the language/country code as the accent ("IT", "ro"); keep only real labels.
            accent=accent if len(accent) > 2 else None,
            compatible_models=["*"],
            meta={k: v for k, v in meta.items() if v not in (None, "", [])},
        ))
    return voices


class CereProcSyncer(DocsOnlySyncer):
    provider_id = "cereproc"
    source = "mixed"
    tts_docs = [
        _API,
        _API + "static/doc_file.json",
        "https://app.cereproc.com/cloud-credits/one-million",
    ]
    tts_guidance = (
        "/speak has no model parameter: return one model for the CereVoice Cloud service with the documented "
        "audio formats, SSML support and streaming option. Leave languages empty (filled from the voice list). "
        "Price per character in the published currency from CereProc's own credit store, with the free tier."
    )

    async def sync(self) -> SyncResult:
        result = await super().sync()
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await get_with_retry(client, VOICE_LIST)
            resp.raise_for_status()
            voices = parse_voices(resp.json())
        _fill_model_languages(result.tts_models, voices)
        result.tts_voices = voices
        result.source = self.source
        result.api_urls = [VOICE_LIST]
        result.notes = f"docs: {len(result.tts_models)} TTS models; api: {len(voices)} voices."
        return result


def _fill_model_languages(models: list[SyncModel], voices: list[SyncVoice]) -> None:
    """The service's languages = the union of its voices' languages (only where the docs gave none)."""
    langs = sorted({lang for v in voices for lang in v.languages})
    for m in models:
        if not m.languages:
            m.languages = langs
