"""
Gradium (Kyutai spin-off) — TTS, STT, speech-to-speech translation.

Source: mixed
  - Models: docs. The API selects models by alias (`model_name`: "default", "stt-translate",
    "s2s-translate", …) and has no list endpoint — extracted into .sync-cache/ (see CLAUDE.md).
  - TTS voices: GET https://api.gradium.ai/api/voices/?include_catalog=true (x-api-key), paginated
    with skip/limit. Only `is_catalog` voices are published — the same listing also returns the
    caller's own cloned/designed voices, which are never published.

Voice locales may carry a private-use dialect subtag ("en-us-x-southern"): the language keeps the
region (en-US); the dialect goes to accent/meta.
"""

from __future__ import annotations

import asyncio

import httpx

from naaviq.config import settings
from naaviq.sync.ai_parser import parse_models_from_docs
from naaviq.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncResult, SyncVoice, get_with_retry
from naaviq.sync.language import accent_from_languages, normalize_languages

_VOICES_URL = "https://api.gradium.ai/api/voices/"
_PAGE = 500
_DOCS = [
    "https://docs.gradium.ai/guides/text-to-speech.md",
    "https://docs.gradium.ai/guides/speech-to-text.md",
    "https://docs.gradium.ai/guides/transcription-settings.md",
    "https://docs.gradium.ai/guides/speech-to-speech-settings.md",
    "https://docs.gradium.ai/guides/voice-settings.md",
    "https://gradium.ai/pricing",
]
_GUIDANCE = (
    "Return every model alias the API accepts in `model_name` for this modality (ids are aliases such as "
    "'default'); record other aliases routing to the same model in meta.aliases. Languages from the "
    "language parameter docs. Credit-based pricing goes in meta, not pricing."
)
_GENDER = {"female": "female", "male": "male"}
_ACCENT_TAGS = {"accent", "region"}


class GradiumSyncer(ProviderSyncer):
    provider_id = "gradium"
    source = "mixed"

    async def sync(self) -> SyncResult:
        if not settings.gradium_api_key:
            raise ValueError("GRADIUM_API_KEY is not set in .env")
        raw_voices, (stt, _), (tts, _), (sts, _) = await asyncio.gather(
            self._fetch_voices(),
            parse_models_from_docs(_DOCS, self.provider_id, "stt", _GUIDANCE),
            parse_models_from_docs(_DOCS, self.provider_id, "tts", _GUIDANCE),
            parse_models_from_docs(_DOCS, self.provider_id, "sts", _GUIDANCE),
        )
        voices = parse_voices(raw_voices)
        return SyncResult(
            stt_models=stt, tts_models=tts, sts_models=sts, tts_voices=voices,
            source=self.source, api_urls=[_VOICES_URL], docs_urls=_DOCS,
            notes=f"{len(voices)} catalog voices; {len(stt)} STT, {len(tts)} TTS, {len(sts)} S2S models (docs).",
        )

    async def _fetch_voices(self) -> list[dict]:
        out: list[dict] = []
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers={"x-api-key": settings.gradium_api_key}) as c:
            for page in range(200):
                resp = await get_with_retry(c, _VOICES_URL, params={
                    "include_catalog": "true", "skip": page * _PAGE, "limit": _PAGE})
                resp.raise_for_status()
                batch = resp.json()
                out += batch
                if len(batch) < _PAGE:
                    break
        return out


def _split_locale(locale: str) -> tuple[str | None, str | None]:
    """'en-us-x-southern' → ('en-US', 'southern')."""
    if not locale:
        return None, None
    base, _, private = locale.lower().partition("-x-")
    return normalize_languages([base])[0], (private or None)


def parse_voices(raw: list[dict]) -> list[SyncVoice]:
    out, seen = [], set()
    for v in raw:
        uid = v.get("uid")
        if not uid or not v.get("is_catalog") or uid in seen:
            continue  # user-owned (cloned / designed) voices are never published
        seen.add(uid)
        lang, dialect = _split_locale(v.get("locale") or v.get("language") or "")
        tags = v.get("tags") or []
        by_cat: dict[str, list[str]] = {}
        for t in tags:
            by_cat.setdefault(t.get("category"), []).append(t.get("value"))
        accent_tag = next((x for x in by_cat.get("accent", []) if x), None)
        accent = (accent_tag or dialect or accent_from_languages([lang] if lang else []))
        meta: dict = {}
        if dialect:
            meta["dialect"] = dialect
        for cat in ("texture", "character-type", "pitch"):
            if by_cat.get(cat):
                meta[cat.replace("-", "_")] = sorted(set(by_cat[cat]))
        out.append(SyncVoice(
            voice_id=uid,
            display_name=v.get("name") or uid,
            gender=_GENDER.get((v.get("gender") or "").lower()),
            category="premade",
            languages=[lang] if lang else [],
            description=v.get("description"),
            accent=accent,
            age=(v.get("age") or "").lower().replace("-", " ") or None,
            use_cases=sorted(set(by_cat.get("use-case", []))),
            tags=sorted({x.lower() for x in by_cat.get("emotion", [])}),
            compatible_models=["*"],
            meta=meta,
        ))
    return out
