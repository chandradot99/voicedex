"""
Amazon Polly sync script.

Source: GET https://polly.{region}.amazonaws.com/v1/voices (API)
  - TTS voices only — Polly is a TTS-only service (stt_models=[])
  - TTS models derived from unique SupportedEngines values in the voice list
  - Paginated via NextToken — all pages are fetched and merged

Voice API fields used:
  Id                    → voice_id  (e.g., "Joanna", "Matthew")
  Name                  → display_name
  Gender                → gender
  LanguageCode          → primary language
  AdditionalLanguageCodes → secondary languages for bilingual voices
  SupportedEngines      → ["neural", "standard", "long-form", "generative"]
                          → compatible_models via _ENGINE_TO_MODEL

Auth: AWS Signature V4 using AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + AWS_REGION.
Signing is implemented with stdlib (hmac + hashlib) — no boto3 needed.

Docs path (AmazonPollyDocsSyncer, the registered syncer while DescribeVoices is unavailable to us): voices come
from the "Available voices" table in the AWS developer guide (its keyless Markdown rendition), parsed into the
same shape DescribeVoices returns so both paths emit identical voice/model ids. Engine models (formats, limits,
regions, prices) come from the engine pages via the docs cache; their languages are derived from the voice table.
To switch back to the API, point the registry entry at AmazonPollySyncer.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from voicedex.config import settings
from voicedex.sync.base import (
    HTTP_TIMEOUT,
    ProviderSyncer,
    SyncModel,
    SyncResult,
    SyncVoice,
    get_with_retry,
)
from voicedex.sync.docs_only import DocsOnlySyncer
from voicedex.sync.language import ACCENT_MAP, normalize_languages

_SERVICE = "polly"
_VOICES_PATH = "/v1/voices"

# Engine name → our model_id
_ENGINE_TO_MODEL: dict[str, str] = {
    "neural":    "polly-neural",
    "standard":  "polly-standard",
    "long-form": "polly-long-form",
    "generative": "polly-generative",
}

# Engine name → display name
_ENGINE_DISPLAY: dict[str, str] = {
    "neural":    "Polly Neural",
    "standard":  "Polly Standard",
    "long-form": "Polly Long-Form",
    "generative": "Polly Generative",
}

# Model priority for is_default — generative > neural > long-form > standard
_DEFAULT_PRIORITY = ["generative", "neural", "long-form", "standard"]


class AmazonPollySyncer(ProviderSyncer):
    provider_id = "amazon-polly"
    source = "api"

    async def sync(self) -> SyncResult:
        voices_data = await self._fetch_all_voices()
        tts_voices = self._parse_voices(voices_data)
        tts_models = self._derive_tts_models(voices_data)
        return SyncResult(
            stt_models=[],
            tts_models=tts_models,
            tts_voices=tts_voices,
            source=self.source,
            api_urls=["https://polly.{region}.amazonaws.com/v1/voices"],
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _fetch_all_voices(self) -> list[dict]:
        if not settings.aws_access_key_id:
            raise ValueError("AWS_ACCESS_KEY_ID is not set in .env")
        if not settings.aws_secret_access_key:
            raise ValueError("AWS_SECRET_ACCESS_KEY is not set in .env")

        region = settings.aws_region or "us-east-1"
        host = f"polly.{region}.amazonaws.com"
        all_voices: list[dict] = []
        next_token: str | None = None

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            while True:
                params: dict[str, str] = {}
                if next_token:
                    params["NextToken"] = next_token

                headers = _sigv4_headers(
                    method="GET",
                    host=host,
                    path=_VOICES_PATH,
                    params=params,
                    region=region,
                    access_key=settings.aws_access_key_id,
                    secret_key=settings.aws_secret_access_key,
                )

                url = f"https://{host}{_VOICES_PATH}"
                if params:
                    url += "?" + urlencode(params)

                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                body = resp.json()

                all_voices.extend(body.get("Voices", []))

                next_token = body.get("NextToken")
                if not next_token:
                    break

        return all_voices

    def _parse_voices(self, voices_data: list[dict]) -> list[SyncVoice]:
        voices: list[SyncVoice] = []

        for v in voices_data:
            primary = v.get("LanguageCode", "")
            additional = v.get("AdditionalLanguageCodes") or []
            all_locales = [primary] + additional
            languages = normalize_languages([_polly_locale(loc) for loc in all_locales if loc])

            supported_engines = v.get("SupportedEngines") or []
            compatible_models = [
                _ENGINE_TO_MODEL[e]
                for e in supported_engines
                if e in _ENGINE_TO_MODEL
            ]

            accent = _accent_from_locale(primary)

            voices.append(SyncVoice(
                voice_id=v["Id"],
                display_name=v.get("Name", v["Id"]),
                gender=v.get("Gender", "").lower() or None,
                category="premade",
                languages=languages,
                accent=accent,
                compatible_models=compatible_models,
                meta={
                    "language_name": v.get("LanguageName"),
                    "supported_engines": supported_engines,
                },
            ))

        return voices

    def _derive_tts_models(self, voices_data: list[dict]) -> list[SyncModel]:
        """Build one TTS model per unique engine found across all voices."""
        engine_langs: dict[str, set[str]] = {}

        for v in voices_data:
            primary = v.get("LanguageCode", "")
            if not primary:
                continue
            for engine in v.get("SupportedEngines") or []:
                if engine not in _ENGINE_TO_MODEL:
                    continue
                if engine not in engine_langs:
                    engine_langs[engine] = set()
                locales = [primary, *(v.get("AdditionalLanguageCodes") or [])]
                engine_langs[engine].update(normalize_languages([_polly_locale(loc) for loc in locales]))

        # Determine which engine is the default (highest priority present)
        default_engine = next(
            (e for e in _DEFAULT_PRIORITY if e in engine_langs),
            None,
        )

        models: list[SyncModel] = []
        for engine, langs in engine_langs.items():
            models.append(SyncModel(
                model_id=_ENGINE_TO_MODEL[engine],
                display_name=_ENGINE_DISPLAY[engine],
                type="tts",
                languages=sorted(langs),
                streaming=True,
                is_default=(engine == default_engine),
                meta={"engine": engine},
            ))

        # Sort by priority order for consistent output
        priority_index = {e: i for i, e in enumerate(_DEFAULT_PRIORITY)}
        models.sort(key=lambda m: priority_index.get(m.meta.get("engine", ""), 99))
        return models


# ── AWS Signature V4 signing ──────────────────────────────────────────────────

def _sigv4_headers(
    method: str,
    host: str,
    path: str,
    params: dict[str, str],
    region: str,
    access_key: str,
    secret_key: str,
) -> dict[str, str]:
    """Build Authorization + x-amz-date headers for a GET request using SigV4."""
    now = datetime.now(timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")

    canonical_querystring = urlencode(sorted(params.items()))
    canonical_headers = f"host:{host}\nx-amz-date:{amz_date}\n"
    signed_headers = "host;x-amz-date"
    payload_hash = hashlib.sha256(b"").hexdigest()

    canonical_request = "\n".join([
        method,
        path,
        canonical_querystring,
        canonical_headers,
        signed_headers,
        payload_hash,
    ])

    credential_scope = f"{date_stamp}/{region}/{_SERVICE}/aws4_request"
    string_to_sign = "\n".join([
        "AWS4-HMAC-SHA256",
        amz_date,
        credential_scope,
        hashlib.sha256(canonical_request.encode()).hexdigest(),
    ])

    signing_key = _get_signing_key(secret_key, date_stamp, region, _SERVICE)
    signature = hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()

    authorization = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    return {
        "x-amz-date": amz_date,
        "Authorization": authorization,
    }


def _get_signing_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    k_date    = _hmac_sha256(f"AWS4{secret_key}".encode(), date_stamp)
    k_region  = _hmac_sha256(k_date, region)
    k_service = _hmac_sha256(k_region, service)
    return _hmac_sha256(k_service, "aws4_request")


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _accent_from_locale(locale: str) -> str | None:
    """Derive accent from BCP-47 locale. e.g., 'en-GB' → 'british'."""
    if locale in _LOCALE_ACCENTS:
        return _LOCALE_ACCENTS[locale]
    parts = locale.split("-")
    if len(parts) >= 2:
        return ACCENT_MAP.get(parts[1].upper())
    return None


# Polly language codes that aren't plain language-REGION pairs.
_LOCALE_FIX = {
    "arb": "ar",            # Modern Standard Arabic
    "en-GB-WLS": "en-GB",   # Welsh English (accent kept below)
}
_LOCALE_ACCENTS = {"en-GB-WLS": "welsh"}


def _polly_locale(locale: str) -> str:
    return _LOCALE_FIX.get(locale.strip(), locale.strip())


# ── Docs path: the "Available voices" table ──────────────────────────────────

VOICES_DOC = "https://docs.aws.amazon.com/polly/latest/dg/available-voices.html"
VOICES_DOC_MD = "https://docs.aws.amazon.com/polly/latest/dg/available-voices.md"
_DG = "https://docs.aws.amazon.com/polly/latest/dg/"

# Table column header → DescribeVoices engine name.
_ENGINE_COLUMNS = {
    "generative voice": "generative",
    "long form voice": "long-form",
    "neural voice": "neural",
    "standard voice": "standard",
}


def _cell_lines(cell: str) -> list[str]:
    return [re.sub(r"[*\\]", "", part).strip() for part in re.split(r"<br\s*/?>", cell)]


def _ascii(name: str) -> str:
    """'Céline' → 'Celine': Polly voice ids are the ASCII-folded voice names (see the API's VoiceId enum)."""
    return unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()


def parse_voice_table(markdown: str) -> list[dict]:
    """The developer guide's voice table → DescribeVoices-shaped dicts (Id, Name, Gender, LanguageCode,
    AdditionalLanguageCodes, SupportedEngines, plus Age for "(child)" voices).

    One table row per language holds one line per voice in each cell. Bilingual voices appear under each of
    their languages; they are merged (first language = LanguageCode, the rest = AdditionalLanguageCodes)."""
    lines = [ln for ln in markdown.splitlines() if ln.strip().startswith("|")]
    header_idx = next((i for i, ln in enumerate(lines) if "Name/ID" in ln), None)
    if header_idx is None:
        raise ValueError("Polly voice table not found (no 'Name/ID' header)")
    header = [c.strip().lower() for c in lines[header_idx].strip().strip("|").split("|")]
    col = {name: i for i, name in enumerate(header)}
    engine_cols = {_ENGINE_COLUMNS[h]: i for h, i in col.items() if h in _ENGINE_COLUMNS}
    if len(engine_cols) != len(_ENGINE_COLUMNS):
        raise ValueError(f"Polly voice table: unexpected engine columns {header}")
    i_lang, i_code, i_name, i_gender = col["language and language variants"], col["language code"], col["name/id"], col["gender"]

    by_id: dict[str, dict] = {}
    for ln in lines[header_idx + 2:]:
        cells = ln.strip().strip("|").split("|")
        if len(cells) < len(header):
            continue
        code = _cell_lines(cells[i_code])[0]
        language_name = _cell_lines(cells[i_lang])[0]
        names = _cell_lines(cells[i_name])
        genders = _cell_lines(cells[i_gender])
        flags = {e: _cell_lines(cells[i]) for e, i in engine_cols.items()}
        for n, raw in enumerate(names):
            if not raw:
                continue
            display = raw.split("/")[0].strip()                # "Céline/Celine" → "Céline"
            voice_id = _ascii(raw.split("/")[-1].strip())       # → "Celine"
            gender_cell = genders[n] if n < len(genders) else ""
            engines = [e for e in _ENGINE_TO_MODEL if n < len(flags[e]) and flags[e][n].lower() == "yes"]
            v = by_id.get(voice_id)
            if v is None:
                by_id[voice_id] = {
                    "Id": voice_id,
                    "Name": display,
                    "Gender": gender_cell.split("(")[0].strip(),
                    "Age": "child" if "child" in gender_cell.lower() else None,
                    "LanguageCode": code,
                    "LanguageName": language_name,
                    "AdditionalLanguageCodes": [],
                    "SupportedEngines": engines,
                }
            else:
                if code != v["LanguageCode"] and code not in v["AdditionalLanguageCodes"]:
                    v["AdditionalLanguageCodes"].append(code)
                v["SupportedEngines"] += [e for e in engines if e not in v["SupportedEngines"]]
    return list(by_id.values())


class AmazonPollyDocsSyncer(DocsOnlySyncer):
    """Keyless: voices from the developer guide's voice table, engine models from the docs cache."""
    provider_id = "amazon-polly"
    source = "docs"
    tts_docs = [
        _DG + "voice-engines-polly.html",
        _DG + "generative-voices.html",
        _DG + "long-form-voices.html",
        _DG + "neural-voices.html",
        _DG + "standard-voices.html",
        _DG + "limits.html",
        _DG + "supportedtags.html",
        "https://aws.amazon.com/polly/pricing/",
    ]
    tts_guidance = (
        "Polly has no model parameter: a request selects an Engine. Return one model per documented engine, "
        "model_id = 'polly-' + the engine's API value (e.g. 'long-form' → 'polly-long-form'), with that engine's "
        "documented sample rates, output formats, SynthesizeSpeech text limit, regions and per-character price. "
        "Leave languages empty (derived from the voice table). Default = the most capable generally available engine."
    )

    async def sync(self) -> SyncResult:
        result = await super().sync()
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"}) as client:
            resp = await get_with_retry(client, VOICES_DOC_MD)
            resp.raise_for_status()
            rows = parse_voice_table(resp.text)

        api = AmazonPollySyncer()
        voices = api._parse_voices(rows)
        for v, row in zip(voices, rows):
            v.age = row.get("Age")
        derived = {m.model_id: m for m in api._derive_tts_models(rows)}
        for m in result.tts_models:
            if not m.languages and m.model_id in derived:
                m.languages = derived[m.model_id].languages

        result.tts_voices = voices
        result.source = self.source
        result.docs_urls = list(dict.fromkeys([VOICES_DOC, *result.docs_urls]))
        result.notes = f"docs: {len(result.tts_models)} TTS models; voice table: {len(voices)} voices."
        return result


# ── Local runner ──────────────────────────────────────────────────────────────

async def _main() -> None:
    import sys

    syncer = AmazonPollySyncer()
    try:
        result = await syncer.sync()
    except ValueError as e:
        print(f"\nError: {e}", file=sys.stderr)
        raise SystemExit(1)
    except httpx.HTTPStatusError as e:
        print(f"\nPolly API error ({e.response.status_code}): {e.response.text[:300]}", file=sys.stderr)
        raise SystemExit(1)

    print(f"\n=== TTS Models ({len(result.tts_models)}) ===")
    for m in result.tts_models:
        print(
            f"  {m.model_id!r:25} {m.display_name!r:22} "
            f"langs={len(m.languages)} is_default={m.is_default}"
        )

    print(f"\n=== TTS Voices ({len(result.tts_voices)}) — showing first 20 ===")
    for v in result.tts_voices[:20]:
        print(
            f"  {v.voice_id!r:15} {v.display_name!r:15} "
            f"gender={v.gender or '?':6} langs={v.languages} "
            f"models={v.compatible_models}"
        )
    if len(result.tts_voices) > 20:
        print(f"  ... and {len(result.tts_voices) - 20} more")

    print(f"\nSource: {result.source}")
    print(f"Fetched at: {result.fetched_at}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(_main())
