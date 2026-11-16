"""
Google Cloud sync script.

Source: mixed
  - TTS voices : GET https://texttospeech.googleapis.com/v1/voices (API, single response)
  - TTS models : AI-parsed from https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types
  - STT models : AI-parsed from https://docs.cloud.google.com/speech-to-text/docs/transcription-model

Auth: X-goog-api-key header (API key restricted to Text-to-Speech API).

Two kinds of TTS "model":
  - Voice tiers (Standard, Wavenet, Neural2, Studio, Chirp-HD, Chirp3-HD, …), encoded in
    locale-prefixed voice names ("en-US-Chirp3-HD-Achernar"). Docs give tier details; any
    tier seen in voice names but missing from the docs is injected as a minimal model so no
    voice is orphaned.
  - Gemini TTS models (gemini-*-tts), selected with a `model` parameter and used with the
    bare-named voices ("Achernar", "Kore", …) the API also returns.

STT models: docs give descriptions, pricing, defaults and streaming flags; when Google
Application Default Credentials are available (`gcloud auth application-default login` +
GOOGLE_CLOUD_PROJECT), the Speech-to-Text v2 Locations API then supplies the authoritative
per-model languages, regions and features, and adds callable models the docs table omits.
The Locations API rejects API keys, hence ADC. Without ADC, STT is docs-only.

Voices fetch, TTS model parse, and STT model parse run concurrently.
"""

from __future__ import annotations

import asyncio

import httpx

from naaviq.config import settings
from naaviq.sync.ai_parser import AIParserError, parse_models_from_docs
from naaviq.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncModel, SyncResult, SyncVoice
from naaviq.sync.language import accent_from_languages, normalize_languages

_VOICES_URL = "https://texttospeech.googleapis.com/v1/voices"
_STT_LOCATIONS_URL = "https://speech.googleapis.com/v2/projects/{project}/locations"

# Locations API feature → canonical capability. Everything else lands in meta.features.
_STT_FEATURE_CAPS = {
    "word_timestamps":         "word_timestamps",
    "automatic_punctuation":   "punctuation",
    "profanity_filter":        "profanity_filter",
    "speech_adaptation_boost": "custom_vocabulary",
    "speaker_diarization":     "speaker_diarization",
}

_TTS_MODELS_DOCS_URLS = [
    "https://docs.cloud.google.com/text-to-speech/docs/list-voices-and-types",
    "https://docs.cloud.google.com/text-to-speech/docs/chirp3-hd",
    "https://docs.cloud.google.com/text-to-speech/docs/gemini-tts",
    "https://docs.cloud.google.com/text-to-speech/docs/create-audio-text-streaming",
    "https://cloud.google.com/text-to-speech/pricing",
]
_STT_MODELS_DOCS_URLS = [
    "https://docs.cloud.google.com/speech-to-text/docs/transcription-model",
    "https://docs.cloud.google.com/speech-to-text/docs/speech-to-text-supported-languages",
    "https://docs.cloud.google.com/speech-to-text/docs/models/chirp-3",
    "https://cloud.google.com/speech-to-text/pricing",
]

_GENDER_MAP = {
    "MALE":    "male",
    "FEMALE":  "female",
    "NEUTRAL": "neutral",
    # SSML_VOICE_GENDER_UNSPECIFIED and other values → None
}

_TTS_MODELS_GUIDANCE = (
    "Return (1) every voice tier as a model whose model_id is the exact, case-sensitive tier "
    "segment used in voice names (e.g. the part between locale and voice letter/persona), and "
    "(2) every Gemini TTS model by its exact `model_name`. Exactly one is_default: the model "
    "Google recommends for new applications. ssml capability where the docs say SSML is "
    "supported; per-character (or per-token) pricing as published."
)

_STT_MODELS_GUIDANCE = (
    "Return every Speech-to-Text v2 transcription model by its exact `model` string, including "
    "deprecated ones that still work (with eol_date). Exactly one is_default: the recommended "
    "model. Languages per model from the supported-languages table; regions from per-model "
    "region availability; per-minute pricing."
)


class GoogleCloudSyncer(ProviderSyncer):
    provider_id = "google-cloud"
    source = "mixed"

    async def sync(self) -> SyncResult:
        if not settings.google_cloud_api_key:
            raise ValueError("GOOGLE_CLOUD_API_KEY is not set in .env")

        ai_key = settings.anthropic_api_key or None

        voices_data, stt_api, (tts_models, tts_notes), (stt_models, stt_notes) = await asyncio.gather(
            self._fetch_voices(),
            self._fetch_stt_locations(),
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

        gemini_ids = [m.model_id for m in tts_models if m.model_id.startswith("gemini")]
        tts_voices = self._parse_voices(voices_data, gemini_ids)
        if stt_api is not None:
            stt_models = _enrich_stt_models(stt_models, stt_api)
        tts_models = self._inject_orphan_tiers(tts_models, tts_voices)

        from_cache = any(n.get("source") == "cache" for n in [tts_notes, stt_notes])
        if from_cache:
            notes = (
                f"Voices: {len(tts_voices)} from /v1/voices. "
                f"TTS models: {len(tts_models)} (cache). "
                f"STT models: {len(stt_models)} (cache"
                + (f" + Locations API, {len(stt_api)} models)." if stt_api else ", no ADC — docs only).")
            )
        else:
            total_in  = tts_notes["input_tokens"]  + stt_notes["input_tokens"]
            total_out = tts_notes["output_tokens"] + stt_notes["output_tokens"]
            notes = (
                f"Voices: {len(tts_voices)} from /v1/voices. "
                f"TTS models: {len(tts_models)} from {len(tts_notes['urls_fetched'])} doc page(s). "
                f"STT models: {len(stt_models)} from {len(stt_notes['urls_fetched'])} doc page(s). "
                f"AI: {total_in} in / {total_out} out tokens ({tts_notes['model']})."
            )

        return SyncResult(
            stt_models=stt_models,
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            api_urls=[_VOICES_URL] + ([_STT_LOCATIONS_URL.format(project="{project}")] if stt_api else []),
            docs_urls=_TTS_MODELS_DOCS_URLS + _STT_MODELS_DOCS_URLS,
            notes=notes,
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_voices(self) -> list[dict]:
        """Single-page call — Google returns all voices in one response (no pagination)."""
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(
                _VOICES_URL,
                headers={"X-goog-api-key": settings.google_cloud_api_key},
            )
            resp.raise_for_status()
            return resp.json().get("voices", [])

    async def _fetch_stt_locations(self) -> dict[str, dict] | None:
        """Per-model availability from the Speech-to-Text v2 Locations API, or None without ADC.

        Returns {model_id: {"languages": set, "locations": set, "features": set, "preview": bool}}.
        """
        token, project = await asyncio.to_thread(_adc_token)
        if not token or not project:
            return None
        headers = {"Authorization": f"Bearer {token}", "x-goog-user-project": project}
        base = _STT_LOCATIONS_URL.format(project=project)
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            location_ids: list[str] = []
            page_token = None
            for _ in range(20):
                params = {"pageSize": 100, **({"pageToken": page_token} if page_token else {})}
                resp = await client.get(base, headers=headers, params=params)
                resp.raise_for_status()
                body = resp.json()
                location_ids += [loc["locationId"] for loc in body.get("locations", [])]
                page_token = body.get("nextPageToken")
                if not page_token:
                    break
            responses = await asyncio.gather(*[client.get(f"{base}/{loc}", headers=headers) for loc in location_ids])

        models: dict[str, dict] = {}
        for loc, resp in zip(location_ids, responses):
            resp.raise_for_status()
            by_lang = resp.json().get("metadata", {}).get("languages", {}).get("models", {})
            for lang, entry in by_lang.items():
                for model_id, feats in (entry.get("modelFeatures") or {}).items():
                    m = models.setdefault(model_id, {"languages": set(), "locations": set(),
                                                     "features": set(), "states": set()})
                    m["languages"].add(lang)
                    m["locations"].add(loc)
                    for f in feats.get("modelFeature") or []:
                        m["features"].add(f.get("feature"))
                        if f.get("feature") == "recognizer":
                            m["states"].add(f.get("releaseState"))
        if not models:
            raise RuntimeError("Speech-to-Text Locations API returned no models — refusing to continue")
        return models

    def _parse_voices(self, items: list[dict], gemini_model_ids: list[str]) -> list[SyncVoice]:
        voices: list[SyncVoice] = []
        for v in items:
            name = v.get("name")
            if not name:
                continue
            languages = normalize_languages(v.get("languageCodes") or [])
            tier = _extract_tier(name)
            if tier is None:
                # Bare persona names ("Kore", "Puck", …) are the Gemini TTS voices.
                if not gemini_model_ids:
                    continue
                compatible, display, persona = list(gemini_model_ids), name, name
            else:
                compatible = [tier]
                suffix = name.split("-")[-1]
                persona = suffix if len(suffix) > 1 else None
                display = suffix if persona else f"{tier} {suffix}"
            voices.append(SyncVoice(
                voice_id=name,
                display_name=display,
                gender=_GENDER_MAP.get(v.get("ssmlGender") or ""),
                category="premade",
                languages=languages,
                accent=accent_from_languages(languages),
                compatible_models=compatible,
                meta={k: val for k, val in {
                    "sample_rate_hz": v.get("naturalSampleRateHertz"),
                    "tier": tier,
                    "persona": persona,
                }.items() if val},
            ))
        return voices

    def _inject_orphan_tiers(
        self,
        models: list[SyncModel],
        voices: list[SyncVoice],
    ) -> list[SyncModel]:
        """
        Add a minimal SyncModel for any tier referenced by voices but missing from the
        AI-parsed docs list. Keeps legacy tiers (Journey, Polyglot, Casual, News) visible
        in the admin diff instead of silently dropping their voices.
        """
        known = {m.model_id for m in models}
        orphans: dict[str, set[str]] = {}
        for v in voices:
            for tier in v.compatible_models:
                if tier not in known:
                    orphans.setdefault(tier, set()).update(v.languages)

        for tier, langs in orphans.items():
            models.append(SyncModel(
                model_id=tier,
                display_name=tier,
                type="tts",
                languages=sorted(langs),
                streaming=False,
                is_default=False,
                description="Legacy tier inferred from voice names (not listed in current tier docs).",
                meta={"is_ga": False, "orphan": True},
            ))
        return models


# ── Helpers ───────────────────────────────────────────────────────────────────

def _adc_token() -> tuple[str | None, str | None]:
    """Access token + project from Application Default Credentials; (None, None) if unavailable."""
    import os
    try:
        import google.auth
        import google.auth.transport.requests
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError:
        return None, None
    try:
        creds, adc_project = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(google.auth.transport.requests.Request())
    except (DefaultCredentialsError, Exception):  # noqa: BLE001 — no/expired ADC → docs-only fallback
        return None, None
    return creds.token, os.getenv("GOOGLE_CLOUD_PROJECT") or adc_project


def _location_region(loc: str) -> str | None:
    """Map a Google location id to the canonical region vocab (asia = APAC)."""
    if loc == "global":
        return "global"
    if loc == "us" or loc.startswith(("us-", "northamerica-")):
        return "us"
    if loc == "eu" or loc.startswith("europe-"):
        return "eu"
    if loc.startswith(("asia-", "australia-")):
        return "asia"
    return None


def _enrich_stt_models(docs_models: list[SyncModel], api: dict[str, dict]) -> list[SyncModel]:
    """API is authoritative for languages / regions / capabilities; docs keep everything else.
    Callable models the docs omit are added from the API alone."""
    by_id = {m.model_id: m for m in docs_models}
    out: list[SyncModel] = []
    for model_id in sorted(set(by_id) | set(api)):
        info = api.get(model_id)
        m = by_id.get(model_id)
        if info is None:
            out.append(m)  # documented but not in any location the project can see — keep docs data
            continue
        caps = sorted({_STT_FEATURE_CAPS[f] for f in info["features"] if f in _STT_FEATURE_CAPS})
        regions = sorted({r for r in (_location_region(loc) for loc in info["locations"]) if r})
        extra = sorted(f for f in info["features"] if f not in _STT_FEATURE_CAPS and f != "recognizer")
        api_meta = {"locations": sorted(info["locations"]), "features": extra}
        # "auto" is the Locations API's key for automatic language detection, not a locale.
        if "auto" in info["languages"]:
            caps = sorted(set(caps) | {"language_detection"})
        languages = sorted(normalize_languages(sorted(info["languages"] - {"auto"})))
        if m is None:
            out.append(SyncModel(
                model_id=model_id,
                display_name=model_id.replace("_", " ").title(),
                type="stt",
                languages=languages,
                lifecycle="beta" if info["states"] == {"PUBLIC_PREVIEW"} else "ga",
                capabilities=caps,
                regions=regions,
                meta={**api_meta, "listed_in_docs": False},
                source="api",
            ))
        else:
            m.languages, m.regions = languages, regions
            m.capabilities = sorted(set(caps) | {c for c in m.capabilities if c not in _STT_FEATURE_CAPS.values()})
            m.meta = {**m.meta, **api_meta}
            out.append(m)
    return out


def _extract_tier(voice_name: str) -> str | None:
    """
    Extract the tier segment from a Google voice name.

    Examples:
        "en-US-Standard-A"        → "Standard"
        "en-US-Wavenet-A"         → "Wavenet"
        "en-US-Neural2-A"         → "Neural2"
        "en-US-Studio-Q"          → "Studio"
        "en-US-Journey-D"         → "Journey"
        "en-US-Chirp-HD-D"        → "Chirp-HD"
        "en-US-Chirp3-HD-Aoede"   → "Chirp3-HD"
        "cmn-CN-Wavenet-A"        → "Wavenet"
    """
    parts = voice_name.split("-")
    if len(parts) < 4:
        return None
    # parts[0:2] is the locale (e.g., en-US, cmn-CN); parts[2] is the tier root.
    # If parts[3] is "HD", fold it into the tier (Chirp-HD, Chirp3-HD).
    if len(parts) >= 5 and parts[3] == "HD":
        return f"{parts[2]}-HD"
    return parts[2]


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = GoogleCloudSyncer()
    try:
        result = await syncer.sync()
    except (ValueError, AIParserError, RuntimeError) as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise SystemExit(1)
    except httpx.HTTPStatusError as e:
        print(
            f"\nGoogle Cloud API error ({e.response.status_code}): {e.response.text[:300]}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print(f"\n=== STT Models ({len(result.stt_models)}) ===")
    for m in result.stt_models:
        marker = " [default]" if m.is_default else ""
        print(f"  {m.model_id!r:25} {m.display_name!r:30} langs={len(m.languages)}{marker}")
        if m.meta:
            print(f"    meta: {m.meta}")

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        marker = " [default]" if m.is_default else ""
        orphan = " (orphan)" if m.meta.get("orphan") else ""
        print(f"  {m.model_id!r:25} {m.display_name!r:30} langs={len(m.languages)}{marker}{orphan}")
        if m.meta:
            print(f"    meta: {m.meta}")

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) — showing first 20 ===")
    for v in result.tts_voices[:20]:
        print(
            f"  {v.voice_id!r:40} models={v.compatible_models!r:15} "
            f"gender={v.gender} accent={v.accent} lang={v.languages}"
        )
    if len(result.tts_voices) > 20:
        print(f"  ... and {len(result.tts_voices) - 20} more")

    print(f"\nSource: {result.source}")
    print(f"Notes:  {result.notes}")


if __name__ == "__main__":
    asyncio.run(_main())
