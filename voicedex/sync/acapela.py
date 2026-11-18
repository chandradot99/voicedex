"""
Acapela Group — Acapela Cloud: REST text-to-speech (streamed or file output) over the Acapela voice portfolio.

Source: mixed. The model comes from the Acapela Cloud docs (https://www.acapela-cloud.com/docs_api/ — the
/api/command/ parameters: audio types, sample rates, text limits, events — plus /docs_tags/ for SSML and voice
tags). There is no model parameter: a request names a voice (e.g. "<Speaker>22k_HQ"), so the catalog carries one
model for the service. Voices come from Acapela Cloud's public, keyless voice list (GET /api/voice/, the list the
product page renders), with name/speaker/gender/locale/age/mood per voice. Locales are ISO 639-3 + country
alpha-3 ("eng-gbr"), mapped to BCP-47 here. Gender codes: "1" female, "2" male (as the API reports them).
Prices are credit packs shown only after login, so none are recorded.
"""

from __future__ import annotations

import httpx

from voicedex.sync.base import HTTP_TIMEOUT, SyncModel, SyncResult, SyncVoice, get_with_retry
from voicedex.sync.docs_only import DocsOnlySyncer
from voicedex.sync.language import normalize_languages

_SITE = "https://www.acapela-cloud.com/"
VOICE_LIST = _SITE + "api/voice/"

_GENDERS = {"1": "female", "2": "male"}
# ISO 3166 alpha-3 → alpha-2 for the countries Acapela uses, plus Acapela's own regional codes.
_COUNTRY = {
    "sau": "SA", "aus": "AU", "bel": "BE", "bra": "BR", "gbr": "GB", "can": "CA", "esp": "ES", "cze": "CZ",
    "dnk": "DK", "nld": "NL", "fro": "FO", "fin": "FI", "fra": "FR", "deu": "DE", "grc": "GR", "ind": "IN",
    "ita": "IT", "jpn": "JP", "kor": "KR", "chn": "CN", "nor": "NO", "pol": "PL", "prt": "PT", "rus": "RU",
    "swe": "SE", "tur": "TR", "usa": "US", "mex": "MX", "che": "CH", "aut": "AT", "irl": "IE", "zaf": "ZA",
    "nzl": "NZ", "arg": "AR", "chl": "CL", "col": "CO", "hkg": "HK", "twn": "TW", "isr": "IL", "egy": "EG",
}
# Locales that are not language-country pairs.
_LOCALE_FIX = {
    "eng-sct": ["en-GB"],          # Scottish English
    "eng-ara": ["en", "ar"],       # bilingual Arabic/English voice
    "sws-got": ["sv-SE"],          # Gothenburg Swedish
    "sws-sca": ["sv-SE"],          # Scanian (southern Swedish)
    "fao-fro": ["fo-FO"],          # Faroese (no ISO 639-3 → 1 entry in the shared table)
}
_ACCENTS = {
    "eng-usa": "american", "eng-gbr": "british", "eng-aus": "australian", "eng-can": "canadian",
    "eng-ind": "indian", "eng-sct": "scottish", "sws-got": "gothenburg", "sws-sca": "scanian",
}


def _languages(locale: str, language_label: str) -> list[str]:
    loc = (locale or "").strip().lower()
    if loc in _LOCALE_FIX:
        return _LOCALE_FIX[loc]
    lang, _, country = loc.partition("-")
    if not lang:
        return []
    if language_label == "USSpanish":  # Acapela labels its "spa-mex" voices US Spanish
        return ["es-US"]
    region = _COUNTRY.get(country)
    return normalize_languages([f"{lang}-{region}" if region else lang])


def parse_voices(rows: list[dict]) -> list[SyncVoice]:
    """GET /api/voice/ → one voice per API voice name (the exact `voice` value for /api/command/)."""
    voices = []
    for r in rows:
        name = (r.get("name") or "").strip()
        if not name:
            continue
        speaker = (r.get("speaker") or name).strip()
        mood = (r.get("mood") or "").strip()
        display = speaker if not mood or mood == "Neutral" or speaker.endswith(mood) else f"{speaker} ({mood})"
        locale = (r.get("locale") or "").strip()
        meta = {
            "speaker": speaker,
            "locale": locale,
            "acapela_language": r.get("language"),
            "quality": r.get("quality"),
            "voice_type": r.get("type"),
            "mood": mood or None,
            "version": r.get("version"),
        }
        voices.append(SyncVoice(
            voice_id=name,
            display_name=display,
            gender=_GENDERS.get(str(r.get("gender") or "").strip()),
            category="premade",
            languages=_languages(locale, r.get("language") or ""),
            accent=_ACCENTS.get(locale.lower()),
            age=(r.get("age") or "").strip().lower() or None,
            tags=[mood.lower()] if mood and mood != "Neutral" else [],
            compatible_models=["*"],
            meta={k: v for k, v in meta.items() if v not in (None, "", [])},
        ))
    return voices


class AcapelaSyncer(DocsOnlySyncer):
    provider_id = "acapela"
    source = "mixed"
    tts_docs = [
        _SITE + "docs_api/",
        _SITE + "docs_tags/",
        _SITE + "docs_product/",
    ]
    tts_guidance = (
        "The command API has no model parameter: return one model for the Acapela Cloud TTS service with the "
        "documented audio types, sample rates, text limits and output modes. Leave languages empty (filled "
        "from the voice list). Prices only if Acapela publishes a per-unit number."
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
