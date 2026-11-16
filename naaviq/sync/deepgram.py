"""
Deepgram sync script.

Source: GET https://api.deepgram.com/v1/models (API)
  - stt[] → STT models (one entry per model per language — deduplicated by canonical_name)
  - tts[] → TTS models (deduplicated by architecture) + TTS voices (one per entry)
"""

from __future__ import annotations

import httpx

from naaviq.config import settings
from naaviq.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncModel, SyncResult, SyncVoice
from naaviq.sync.language import normalize_languages

_API_URL = "https://api.deepgram.com/v1/models"

# Deepgram's API doesn't flag a default. Pick the first of these that the API
# actually returns (so a removed model never becomes a phantom default).
_STT_DEFAULT_PREFERENCE = ["nova-3-general", "nova-3", "nova-2-general"]
_TTS_DEFAULT_PREFERENCE = ["aura-2", "aura"]

_MASCULINE_TAGS = {"masculine"}
_FEMININE_TAGS  = {"feminine"}


class DeepgramSyncer(ProviderSyncer):
    provider_id = "deepgram"
    source = "api"

    async def sync(self) -> SyncResult:
        data = await self._fetch_raw()
        stt_models, tts_models = self._parse_models(data)
        tts_voices = self._parse_voices(data)
        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            api_urls=[_API_URL],
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_raw(self) -> dict:
        if not settings.deepgram_api_key:
            raise ValueError("DEEPGRAM_API_KEY is not set in .env")
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(
                _API_URL,
                headers={"Authorization": f"Token {settings.deepgram_api_key}"},
            )
            resp.raise_for_status()
            return resp.json()

    def _parse_models(self, data: dict) -> tuple[list[SyncModel], list[SyncModel]]:
        """Returns (stt_models, tts_models)."""

        # STT — Deepgram returns one entry per model per language, deduplicate by canonical_name
        # Each per-language entry carries its own streaming/batch flags, so a model
        # supports a mode if ANY of its language entries does.
        stt_entries: dict[str, list[dict]] = {}
        for m in data.get("stt", []):
            canonical = m.get("canonical_name") or m.get("name")
            if not canonical or not _is_real_model_id(canonical):
                continue
            stt_entries.setdefault(canonical, []).append(m)

        stt_default = _pick_default(stt_entries.keys(), _STT_DEFAULT_PREFERENCE)
        stt_models: list[SyncModel] = []
        for canonical, entries in stt_entries.items():
            first = entries[0]
            langs = {lang for e in entries for lang in normalize_languages(e.get("languages", []))}
            stt_models.append(SyncModel(
                model_id=canonical,
                display_name=_display_name_from_id(canonical),
                type="stt",
                languages=sorted(langs),
                streaming=any(e.get("streaming", False) for e in entries),
                is_default=canonical == stt_default,
                meta={
                    "architecture":     first.get("architecture"),
                    "version":          max((e.get("version") or "" for e in entries), default="") or None,
                    "batch":            any(e.get("batch", False) for e in entries),
                    "formatted_output": any(e.get("formatted_output", False) for e in entries),
                    "multilingual":     any(e.get("multilingual", False) for e in entries),
                },
            ))

        # TTS models — deduplicate by architecture, collect all languages across voices
        arch_langs: dict[str, set[str]] = {}

        for m in data.get("tts", []):
            arch = m.get("architecture")
            if not arch:
                continue
            if arch not in arch_langs:
                arch_langs[arch] = set()
            for lang in normalize_languages(m.get("languages", [])):
                arch_langs[arch].add(lang)

        tts_default = _pick_default(arch_langs.keys(), _TTS_DEFAULT_PREFERENCE)
        tts_models: list[SyncModel] = []
        for arch, langs in arch_langs.items():
            tts_models.append(SyncModel(
                model_id=arch,
                display_name=_display_name_from_id(arch),
                type="tts",
                languages=sorted(langs),
                streaming=True,
                is_default=arch == tts_default,
                meta={},
            ))

        return stt_models, tts_models

    def _parse_voices(self, data: dict) -> list[SyncVoice]:
        voices: list[SyncVoice] = []

        for m in data.get("tts", []):
            canonical = m.get("canonical_name")
            name      = m.get("name", "")
            meta_raw  = m.get("metadata") or {}
            tags      = {t.lower() for t in meta_raw.get("tags", [])}

            # Use API-provided display_name when available (handles accented chars like Álvaro)
            display_name = meta_raw.get("display_name") or name.title()

            voices.append(SyncVoice(
                voice_id=canonical,
                display_name=display_name,
                gender=_gender_from_tags(tags),
                category="premade",
                languages=list(dict.fromkeys(normalize_languages(m.get("languages", [])))),
                preview_url=meta_raw.get("sample"),
                accent=meta_raw.get("accent"),
                age=meta_raw.get("age"),
                use_cases=meta_raw.get("use_cases") or [],
                tags=meta_raw.get("tags") or [],
                compatible_models=[arch] if (arch := m.get("architecture")) else [],
                meta={
                    "color":        meta_raw.get("color"),
                    "image":        meta_raw.get("image"),
                    "version":      m.get("version"),
                    "uuid":         m.get("uuid"),
                },
            ))

        return voices


# ── Helpers ───────────────────────────────────────────────────────────────────

def _display_name_from_id(model_id: str) -> str:
    """Derive a human-readable display name from a model/architecture ID.

    "nova-3-general" → "Nova 3 General"
    "aura-2"         → "Aura 2"
    "whisper-large"  → "Whisper Large"
    """
    return model_id.replace("-", " ").title()


def _is_real_model_id(model_id: str) -> bool:
    """Deepgram's /v1/models leaks internal placeholder entries such as
    "general-dQw4w9WgXcQ". Real model IDs are lowercase slugs."""
    return model_id == model_id.lower()


def _pick_default(available, preference: list[str]) -> str | None:
    ids = set(available)
    return next((p for p in preference if p in ids), None)


def _gender_from_tags(tags: set[str]) -> str | None:
    if tags & _MASCULINE_TAGS:
        return "male"
    if tags & _FEMININE_TAGS:
        return "female"
    return None


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = DeepgramSyncer()
    try:
        result = await syncer.sync()
    except ValueError as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise SystemExit(1)
    except httpx.HTTPStatusError as e:
        print(f"\nDeepgram API error ({e.response.status_code}): {e.response.text[:300]}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        print(f"  {m.model_id!r:35} {m.display_name!r:25} langs={len(m.languages)}")
        if m.meta:
            print(f"    meta: {m.meta}")

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        print(f"  {m.model_id!r:35} {m.display_name!r:25} langs={len(m.languages)}")

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) — showing first 20 ===")
    for v in result.tts_voices[:20]:
        print(f"  {v.voice_id!r:35} {v.display_name!r:20} gender={v.gender} models={v.compatible_models}")
    if len(result.tts_voices) > 20:
        print(f"  ... and {len(result.tts_voices) - 20} more")

    print(f"\nSource: {result.source}")
    print(f"Fetched at: {result.fetched_at}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_main())
