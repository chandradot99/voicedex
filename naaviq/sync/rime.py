"""
Rime AI sync script.

Source: mixed
  - TTS voices: GET https://users.rime.ai/data/voices/voice_details.json (public, no auth)
  - TTS models: AI-parsed from docs (no /models endpoint)
  - STT: not offered — stt_models=[]

Voice catalog is a static JSON file returning all 600+ voices at once (no pagination).

Voice object shape:
  {
    "speaker": "albion",
    "gender": "Male",           -- "Male", "Female", "Non-binary", or ""
    "age": "Young Adult",       -- "Young Adult", "Adult", "Elder", or ""
    "country": "England",
    "dialect": "English",
    "demographic": "White",
    "genre": ["Any"],           -- use case tags; may be comma-separated string inside array
    "modelId": "arcana",        -- "arcana", "mistv3", "mistv2", "mist"
    "lang": "eng",              -- ISO 639-2 three-letter code
    "language": "English",
    "flagship": true
  }

TTS models: parsed from docs (no /models endpoint). Voices are kept only for models the docs list
as callable, so voices of retired models (e.g. Arcana → Coda in 2026) drop out and get deprecated
by the merge rather than pointing at models that no longer exist.

Auth: Bearer token for synthesis only — voice list endpoint is public.
Config: RIME_API_KEY (not needed for sync, reserved for future synthesis use).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

import httpx

from naaviq.sync.ai_parser import parse_models_from_docs
from naaviq.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncResult, SyncVoice
from naaviq.sync.language import normalize_languages

_VOICES_URL = "https://users.rime.ai/data/voices/voice_details.json"

_DOCS_URLS = [
    "https://docs.rime.ai/docs/models",
    "https://docs.rime.ai/docs/voices",
    "https://www.rime.ai/pricing",
]

_MODEL_GUIDANCE = (
    "Return every callable Rime TTS model id (exact `modelId` strings the API accepts). Models "
    "with an announced retirement date stay in, with eol_date and meta.replacement; exclude models "
    "already retired. is_default=true for the model the docs recommend for new applications. "
    "Pricing is per minute of audio when stated that way."
)

# Gender normalization
_GENDER_MAP: dict[str, str] = {
    "male":       "male",
    "female":     "female",
    "non-binary": "neutral",
}

# Country → accent (English voices only; other languages skip accent)
_COUNTRY_TO_ACCENT: dict[str, str] = {
    "england":     "british",
    "uk":          "british",
    "us":          "american",
    "usa":         "american",
    "australia":   "australian",
    "india":       "indian",
    "ireland":     "irish",
    "canada":      "canadian",
    "new zealand": "new_zealander",
    "south africa": "south_african",
}

class RimeSyncer(ProviderSyncer):
    provider_id = "rime"
    source = "mixed"

    async def sync(self) -> SyncResult:
        voices_data, (tts_models, notes) = await asyncio.gather(
            self._fetch_voices(),
            parse_models_from_docs(
                seed_urls=_DOCS_URLS,
                provider_id=self.provider_id,
                model_type="tts",
                guidance=_MODEL_GUIDANCE,
            ),
        )
        tts_voices = self._parse_voices(voices_data, [m.model_id for m in tts_models])

        from_cache = isinstance(notes, dict) and notes.get("source") == "cache"
        sync_notes = (
            f"{len(tts_voices)} voices. {len(tts_models)} TTS models (cache)."
            if from_cache else
            f"{len(tts_voices)} voices. {len(tts_models)} TTS models."
        )

        return SyncResult(
            stt_models=[],
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            api_urls=[_VOICES_URL],
            docs_urls=_DOCS_URLS,
            notes=sync_notes,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_voices(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(_VOICES_URL)
            resp.raise_for_status()
            return resp.json()

    def _parse_voices(self, voices_data: list[dict], model_ids: list[str]) -> list[SyncVoice]:
        """`model_ids` = current models from the docs, best first (default model first)."""
        rank = {m: i for i, m in enumerate(model_ids)}
        # Group by speaker — some voices appear in multiple models with the same or
        # different language. Deduplicate into one record per speaker, collecting
        # all model IDs and unioning all languages.
        by_speaker: dict[str, list[dict]] = defaultdict(list)
        for v in voices_data:
            if v.get("speaker"):
                by_speaker[v["speaker"]].append(v)

        voices: list[SyncVoice] = []
        for speaker, entries in by_speaker.items():
            entries = [e for e in entries if e.get("modelId") in rank]
            if not entries:
                continue  # only available on retired models
            # Metadata from the entry of the best current model
            primary = min(entries, key=lambda e: rank[e["modelId"]])

            gender = _GENDER_MAP.get((primary.get("gender") or "").lower())
            age = _parse_age(primary.get("age") or "")
            accent = _parse_accent(primary.get("country") or "", primary.get("lang") or "")
            use_cases = _parse_genre(primary.get("genre") or [])

            # Union all languages across all model entries for this speaker
            all_langs: list[str] = []
            seen_langs: set[str] = set()
            for entry in entries:
                lang = entry.get("lang") or ""
                if lang and lang not in seen_langs:
                    seen_langs.add(lang)
                    all_langs.append(lang)
            languages = list(dict.fromkeys(normalize_languages(all_langs)))  # ISO 639-2 → 639-1

            # Collect all model IDs in capability order
            model_ids = sorted(
                {e["modelId"] for e in entries if e.get("modelId")},
                key=lambda m: rank[m],
            )

            voices.append(SyncVoice(
                voice_id=speaker,
                display_name=speaker.replace("_", " ").title(),
                gender=gender,
                category="premade",
                languages=languages,
                accent=accent,
                age=age,
                use_cases=use_cases,
                compatible_models=model_ids,
                meta={
                    "country": primary.get("country"),
                    "dialect": primary.get("dialect"),
                    "demographic": primary.get("demographic"),
                    "flagship": primary.get("flagship", False),
                },
            ))
        return voices


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_age(age: str) -> str | None:
    if not age:
        return None
    return age.lower().replace(" ", "_")  # "Young Adult" → "young_adult"


def _parse_accent(country: str, lang: str) -> str | None:
    # Accent is only meaningful for English voices
    if lang != "eng":
        return None
    return _COUNTRY_TO_ACCENT.get(country.lower())


def _parse_genre(genre: list[str]) -> list[str]:
    """Flatten genre tags — entries may be comma-separated strings."""
    use_cases: list[str] = []
    for item in genre:
        for part in item.split(","):
            part = part.strip().lower()
            if part and part != "any":
                use_cases.append(part)
    return use_cases


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = RimeSyncer()
    try:
        result = await syncer.sync()
    except httpx.HTTPStatusError as e:
        print(f"\nRime API error ({e.response.status_code}): {e.response.text[:300]}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        print(
            f"  {m.model_id!r:12} {m.display_name!r:20} "
            f"langs={m.languages} is_default={m.is_default}"
        )

    # Show counts and a sample per model
    from collections import Counter
    model_counts = Counter(v.compatible_models[0] for v in result.tts_voices if v.compatible_models)
    print(f"\n=== TTS Voices ({len(result.tts_voices)}) — by model ===")
    for model_id, count in sorted(model_counts.items()):
        print(f"  {model_id!r:12} {count} voices")

    print("\n=== Sample voices (first 5 per model) ===")
    shown: dict[str, int] = {}
    for v in result.tts_voices:
        model = v.compatible_models[0] if v.compatible_models else "?"
        if shown.get(model, 0) >= 5:
            continue
        shown[model] = shown.get(model, 0) + 1
        print(
            f"  {v.voice_id!r:20} {v.display_name!r:22} "
            f"gender={v.gender or '?':6} accent={v.accent or '?':12} "
            f"age={v.age or '?':12} langs={v.languages}"
        )

    print(f"\nSource: {result.source}")
    print(f"Fetched at: {result.fetched_at}")


if __name__ == "__main__":
    asyncio.run(_main())
