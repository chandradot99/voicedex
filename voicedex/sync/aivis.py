"""
Aivis Cloud API (Aivis Project, JP): Japanese TTS on community voice models, priced in JPY per character.

Source: mixed.
  - Model: docs (aivis-project.com/cloud-api, api.aivis-project.com/v1/docs). The API has no engine/model
    parameter — requests pick a voice by `model_uuid` — so the catalog records one TTS model.
  - Voices: GET https://api.aivis-project.com/v1/aivm-models/search — keyless, paged (limit ≤ 30). One voice per
    public AIVM model (voice id = aivm_model_uuid, the value the synthesis API takes). Uploader account fields and
    free-text descriptions (which carry creators' social links) are never stored.
"""

from __future__ import annotations

import httpx

from voicedex.sync.base import HTTP_TIMEOUT, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.docs_only import DocsOnlySyncer
from voicedex.sync.language import normalize_languages

SEARCH_URL = "https://api.aivis-project.com/v1/aivm-models/search"
_PAGE = 30
_MAX_PAGES = 50

_GENDER = {"Female": "female", "Male": "male", "Neutral": "neutral"}
_AGE = {"Youthful": "young", "Adult": "adult", "MiddleAged": "middle_aged", "Elderly": "old"}


def _timbre(t: str) -> tuple[str | None, str | None]:
    for g, gender in _GENDER.items():
        if t.endswith(g):
            prefix = t[: -len(g)]
            return gender, _AGE.get(prefix)
    return None, None


def parse_voices(rows: list[dict]) -> list[SyncVoice]:
    voices = []
    for r in rows:
        vid = str(r.get("aivm_model_uuid") or "").strip()
        if not vid or r.get("visibility") != "Public":
            continue
        speakers = r.get("speakers") or []
        langs = sorted({lang for s in speakers for lang in (s.get("supported_languages") or [])})
        styles = list(dict.fromkeys(st.get("name") for s in speakers for st in (s.get("styles") or []) if st.get("name")))
        sample = next((vs.get("audio_url") for s in speakers for st in (s.get("styles") or [])
                       for vs in (st.get("voice_samples") or []) if vs.get("audio_url")), None)
        files = r.get("model_files") or []
        gender, age = _timbre(r.get("voice_timbre") or "")
        meta = {
            "styles": styles or None,
            "license": next((f.get("license_type") for f in files if f.get("license_type")), None),
            "architecture": next((f.get("model_architecture") for f in files if f.get("model_architecture")), None),
            "aivm_category": r.get("category"),
            "official": (r.get("user") or {}).get("account_type") == "Official",
        }
        voices.append(SyncVoice(
            voice_id=vid,
            display_name=(r.get("name") or vid).strip(),
            gender=gender,
            age=age,
            category="premade",
            languages=normalize_languages(langs),
            preview_url=sample,
            tags=[t.get("name") if isinstance(t, dict) else str(t) for t in (r.get("tags") or [])],
            compatible_models=["*"],
            meta={k: v for k, v in meta.items() if v is not None},
        ))
    return voices


class AivisSyncer(DocsOnlySyncer):
    provider_id = "aivis"
    source = "mixed"
    tts_docs = [
        "https://aivis-project.com/cloud-api/",
        "https://api.aivis-project.com/v1/docs",
    ]
    tts_guidance = (
        "One record per synthesis model generation/engine the API exposes (not per community voice model). "
        "Price in JPY as published (currency + price)."
    )

    async def sync(self) -> SyncResult:
        result = await super().sync()
        rows: list[dict] = []
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for page in range(1, _MAX_PAGES + 1):
                resp = await get_with_retry(client, SEARCH_URL, params={"page": page, "limit": _PAGE})
                resp.raise_for_status()
                batch = resp.json().get("aivm_models") or []
                rows += batch
                if len(batch) < _PAGE:
                    break
        result.tts_voices = parse_voices(rows)
        result.source = self.source
        result.api_urls = [SEARCH_URL]
        result.notes = f"docs: {len(result.tts_models)} TTS model; api: {len(result.tts_voices)} public voice models."
        return result
