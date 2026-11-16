"""
Cartesia sync script.

Source: mixed
  - TTS voices : GET https://api.cartesia.ai/voices  (cursor-paginated REST API)
  - TTS models : AI-parsed from https://docs.cartesia.ai/build-with-cartesia/tts-models/latest
  - STT models : AI-parsed from https://docs.cartesia.ai/build-with-cartesia/stt-models   (Ink family)

The voice API returns one entry per voice. We filter to public voices (access="public")
(community-cloned and private voices are skipped).

The TTS models page lists family models (sonic-3, sonic-2, sonic-turbo, sonic),
dated snapshots (e.g., sonic-3-2026-01-12), and "-latest" aliases. We return
all of them — each is a real callable model ID — and stash the snapshot/alias
metadata in `meta` so consumers can filter (e.g., is_snapshot=false for the
4-family view). The STT page follows the same convention.

Voices and both parse calls run concurrently via asyncio.gather to keep total
sync latency around the slowest single call (~10s) instead of the sum (~30s).
"""

from __future__ import annotations

import asyncio

import httpx

from naaviq.config import settings
from naaviq.sync.ai_parser import AIParserError, parse_models_from_docs
from naaviq.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncResult, SyncVoice
from naaviq.sync.language import accent_from_languages, normalize_languages

_VOICES_URL = "https://api.cartesia.ai/voices"

_TTS_MODELS_DOCS_URLS = [
    "https://docs.cartesia.ai/build-with-cartesia/tts-models/latest",
    "https://docs.cartesia.ai/build-with-cartesia/tts-models/older-models",
]
_STT_MODELS_DOCS_URLS = [
    "https://docs.cartesia.ai/build-with-cartesia/stt-models",
]

# Latest per docs.cartesia.ai/llms.txt (valid: 2026-08-14, 2026-03-01, 2024-11-13, 2024-06-10).
_CARTESIA_VERSION = "2026-08-14"
_PAGE_SIZE        = 100
_MAX_PAGES        = 50

_GENDER_MAP = {
    "masculine":      "male",
    "feminine":       "female",
    "gender_neutral": "neutral",
}

_META_GUIDANCE = (
    "Set eol_date='YYYY-MM-DD' (top-level field) if the docs mention an end-of-life date. "
    "For every model, populate `meta` with: "
    "parent_model_id — the family root id this model belongs to, or null if it IS a family root; "
    "snapshot_date — 'YYYY-MM-DD' for dated snapshots, else null; "
    "alias_of — for moving aliases (e.g. ids ending in '-latest'), the id they currently point to, else null; "
    "production_recommended — false if the docs warn against using it in production, else true. "
    "Set interfaces from the documented transports (http, websocket). "
)

_TTS_MODELS_GUIDANCE = (
    "Return EVERY callable TTS model id on these pages as a separate model: family roots, dated "
    "snapshots and aliases. Mark exactly one model is_default=true: the newest production-ready "
    "family root. "
    + _META_GUIDANCE
)

_STT_MODELS_GUIDANCE = (
    "Return EVERY callable STT model id on these pages as a separate model: family roots, dated "
    "snapshots and aliases. Mark exactly one model is_default=true: the newest production-ready "
    "family root. "
    + _META_GUIDANCE
)


class CartesiaSyncer(ProviderSyncer):
    provider_id = "cartesia"
    source = "mixed"

    async def sync(self) -> SyncResult:
        if not settings.cartesia_api_key:
            raise ValueError("CARTESIA_API_KEY is not set in .env")

        ai_key = settings.anthropic_api_key or None

        (tts_voices, voice_pages), (tts_models, tts_notes), (stt_models, stt_notes) = await asyncio.gather(
            self._fetch_voices(),
            parse_models_from_docs(
                seed_urls=_TTS_MODELS_DOCS_URLS,
                provider_id=self.provider_id,
                model_type="tts",
                guidance=_TTS_MODELS_GUIDANCE,
                api_key=ai_key,
            ),
            parse_models_from_docs(
                seed_urls=_STT_MODELS_DOCS_URLS,
                provider_id=self.provider_id,
                model_type="stt",
                guidance=_STT_MODELS_GUIDANCE,
                api_key=ai_key,
            ),
        )

        tts_src = tts_notes.get("source", "ai")
        stt_src = stt_notes.get("source", "ai")
        if tts_src == "cache" or stt_src == "cache":
            notes = (
                f"Voices: {len(tts_voices)} from {voice_pages} API page(s). "
                f"TTS models: {len(tts_models)} (cache). "
                f"STT models: {len(stt_models)} (cache)."
            )
        else:
            total_in  = tts_notes["input_tokens"]  + stt_notes["input_tokens"]
            total_out = tts_notes["output_tokens"] + stt_notes["output_tokens"]
            notes = (
                f"Voices: {len(tts_voices)} from {voice_pages} API page(s). "
                f"TTS models: {len(tts_models)} from {len(tts_notes['urls_fetched'])} doc page(s). "
                f"STT models: {len(stt_models)} from {len(stt_notes['urls_fetched'])} doc page(s). "
                f"AI: {total_in} in / {total_out} out tokens ({tts_notes['model']})."
            )

        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            api_urls=[_VOICES_URL],
            docs_urls=_TTS_MODELS_DOCS_URLS + _STT_MODELS_DOCS_URLS,
            notes=notes,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_voices(self) -> tuple[list[SyncVoice], int]:
        """Returns (voices, page_count). Caps at _MAX_PAGES to prevent cursor loops."""
        voices: list[SyncVoice] = []
        starting_after: str | None = None
        pages = 0

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for _ in range(_MAX_PAGES):
                # preview_file_url is not requested: those file links need a Cartesia API key, so they're
                # useless as public sample links (401 for every visitor).
                params: dict = {"limit": _PAGE_SIZE}
                if starting_after:
                    params["starting_after"] = starting_after

                resp = await client.get(
                    _VOICES_URL,
                    headers={
                        "Authorization":   f"Bearer {settings.cartesia_api_key}",
                        "Cartesia-Version": _CARTESIA_VERSION,
                    },
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()
                pages += 1

                items = data.get("data", [])
                for item in items:
                    if not _is_public(item) or item.get("status", "active") != "active":
                        continue
                    voices.append(_to_sync_voice(item))

                if not data.get("has_more", False) or not items:
                    break
                starting_after = items[-1].get("id")
                if not starting_after:
                    break
            else:
                raise RuntimeError(
                    f"Cartesia voice pagination exceeded {_MAX_PAGES} pages — possible cursor loop"
                )

        return voices, pages


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_public(item: dict) -> bool:
    # 2026-08-14 replaced the boolean `is_public` with `access: "public" | "private"`.
    if "access" in item:
        return item.get("access") == "public"
    return bool(item.get("is_public", False))


def _accents(item: dict) -> list[dict]:
    return [a for a in (item.get("accents") or []) if isinstance(a, dict) and a.get("locale")]


def _voice_languages(item: dict) -> list[str]:
    # `language` is deprecated in 2026-08-14 in favour of `accents[].locale` (BCP-47).
    # Native locales first, so languages[0] is the voice's primary language.
    accents = sorted(_accents(item), key=lambda a: not a.get("is_native"))
    if accents:
        return list(dict.fromkeys(normalize_languages([a["locale"] for a in accents])))
    raw_lang = item.get("language") or ""
    return normalize_languages([raw_lang]) if raw_lang else []


def _to_sync_voice(item: dict) -> SyncVoice:
    languages = _voice_languages(item)
    accents = _accents(item)
    native = [a for a in accents if a.get("is_native")]
    primary = normalize_languages([native[0]["locale"]]) if native else languages[:1]

    meta: dict = {
        "tagline":        item.get("tagline"),
        "is_pro":         item.get("is_pro"),
        # Per-locale accent labels as Cartesia names them (e.g. {"en-US": "general-american"}).
        "locale_accents": {normalize_languages([a["locale"]])[0]: a.get("accent") for a in accents} or None,
        "native_locales": normalize_languages([a["locale"] for a in native]) or None,
    }
    return SyncVoice(
        voice_id=item["id"],
        display_name=item.get("name") or item["id"],
        gender=_GENDER_MAP.get(item.get("gender") or ""),
        category="premade",
        languages=languages,
        description=item.get("description"),
        accent=accent_from_languages(primary),
        compatible_models=["*"],
        capabilities=["multilingual_native"] if len(native) > 1 else [],
        meta={k: v for k, v in meta.items() if v is not None},
    )


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = CartesiaSyncer()
    try:
        result = await syncer.sync()
    except (ValueError, AIParserError, RuntimeError) as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise SystemExit(1)
    except httpx.HTTPStatusError as e:
        print(f"\nCartesia API error ({e.response.status_code}): {e.response.text}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        marker = " [default]" if m.is_default else ""
        print(f"  {m.model_id!r:30} {m.display_name!r:30} langs={len(m.languages)}{marker}")
        if m.meta:
            print(f"    meta: {m.meta}")

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        marker = " [default]" if m.is_default else ""
        print(f"  {m.model_id!r:30} {m.display_name!r:30} langs={len(m.languages)}{marker}")
        if m.meta:
            print(f"    meta: {m.meta}")

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) — showing first 20 ===")
    for v in result.tts_voices[:20]:
        print(
            f"  {v.voice_id!r:40} {v.display_name!r:25} "
            f"gender={v.gender} accent={v.accent} lang={v.languages}"
        )
    if len(result.tts_voices) > 20:
        print(f"  ... and {len(result.tts_voices) - 20} more")

    print(f"\nSource: {result.source}")
    print(f"Notes:  {result.notes}")
    print(f"Fetched at: {result.fetched_at}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_main())
