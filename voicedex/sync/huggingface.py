"""
Open-weights speech models from the Hugging Face Hub API (no key needed).

Source: GET https://huggingface.co/api/models?author=<org>&pipeline_tag=<tag>&expand[]=…

One `HuggingFaceSyncer` subclass per publishing org (voicedex/sync/open_weights.py). Every repo the org
publishes under a speech pipeline tag is a candidate; a repo is listed when it clears the popularity bar
(docs/design/provider-expansion.md §1): ≥ MIN_DOWNLOADS_30D downloads in the last 30 days or ≥ MIN_LIKES
likes. Quantised / converted repackagings (GGUF, ONNX, MLX, AWQ, …) are skipped — they are runtimes of a
model we already list, not new models. New releases flow in automatically; nothing is hard-coded.

Records: model id = the HF repo id (e.g. "hexgrad/Kokoro-82M"), `open_weights` = {license, url,
commercial_use}, languages from the model card. Download/like counts are used for the bar only and are
not stored (they change daily and would churn `updated_at`).
"""

from __future__ import annotations

import re
from typing import ClassVar

import httpx

from voicedex.sync.base import HTTP_TIMEOUT, ProviderSyncer, SyncModel, SyncResult, get_with_retry
from voicedex.sync.language import normalize_languages

_API = "https://huggingface.co/api/models"
_EXPAND = ("downloads", "likes", "pipeline_tag", "cardData", "gated", "createdAt", "tags")

MIN_DOWNLOADS_30D = 20_000
MIN_LIKES = 200

PIPELINES: dict[str, str] = {
    "automatic-speech-recognition": "stt",
    "text-to-speech": "tts",
}

_REPACKAGED = re.compile(
    r"(gguf|onnx|mlx|awq|gptq|exl2|int4|int8|fp8|bnb|4bit|8bit|quant|ct2|coreml|openvino|tflite|-hf-?\d*$)",
    re.IGNORECASE,
)
_LANG = re.compile(r"^[a-z]{2,3}(-[A-Z]{2})?$")

# Licences whose commercial-use stance is unambiguous. Anything else → None (not stated / read the licence).
_COMMERCIAL_OK = {
    "apache-2.0", "mit", "bsd-2-clause", "bsd-3-clause", "cc-by-4.0", "cc-by-sa-4.0", "cc0-1.0",
    "openrail", "openrail++", "creativeml-openrail-m", "mpl-2.0", "unlicense", "openmdw-1.0", "openmdw-1.1",
}
_NON_COMMERCIAL = re.compile(r"(^cc-by-nc|non-?commercial|research|^cpml|coqui-public-model)", re.IGNORECASE)


def commercial_use(license_id: str) -> bool | None:
    lic = license_id.lower()
    if lic in _COMMERCIAL_OK:
        return True
    if _NON_COMMERCIAL.search(lic):
        return False
    return None


def _languages(card: dict) -> list[str]:
    raw = card.get("language") or []
    if isinstance(raw, str):
        raw = [raw]
    codes = [c for c in normalize_languages([str(x) for x in raw]) if _LANG.match(c)]
    if not codes and any(str(x).lower() == "multilingual" for x in raw):
        return ["*"]
    return sorted(set(codes))


def _license(card: dict, tags: list[str]) -> str | None:
    lic = card.get("license") or next((t.split(":", 1)[1] for t in tags if t.startswith("license:")), None)
    if isinstance(lic, list):
        lic = lic[0] if lic else None
    if lic == "other":
        return card.get("license_name") or "other"
    return lic


def _display_name(repo_id: str) -> str:
    return repo_id.split("/", 1)[1]


class HuggingFaceSyncer(ProviderSyncer):
    """Subclasses set provider_id and hf_authors; optionally repo_filter / exclude (regex on repo id)."""

    source = "api"
    hf_authors: ClassVar[list[str]] = []
    repo_filter: ClassVar[str | None] = None   # keep only repo ids matching this regex
    exclude: ClassVar[str | None] = None       # drop repo ids matching this regex

    async def sync(self) -> SyncResult:
        rows: list[dict] = []
        urls: list[str] = []
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for author in self.hf_authors:
                for tag in PIPELINES:
                    params = [("author", author), ("pipeline_tag", tag), ("sort", "downloads"),
                              ("direction", "-1"), ("limit", "200")]
                    params += [("expand[]", e) for e in _EXPAND]
                    resp = await get_with_retry(client, _API, params=params)
                    resp.raise_for_status()
                    rows += resp.json()
                    urls.append(f"{_API}?author={author}&pipeline_tag={tag}")

        models = {"stt": [], "tts": []}
        seen: set[str] = set()
        for r in rows:
            m = self._to_model(r)
            if m and m.model_id not in seen:
                seen.add(m.model_id)
                models[m.type].append(m)
        return SyncResult(
            stt_models=models["stt"], tts_models=models["tts"], tts_voices=[],
            source=self.source, api_urls=urls,
            notes=f"{len(models['stt'])} STT + {len(models['tts'])} TTS repos above the bar "
                  f"(≥{MIN_DOWNLOADS_30D:,} downloads/30d or ≥{MIN_LIKES} likes) of {len(rows)} candidates.",
        )

    def _to_model(self, r: dict) -> SyncModel | None:
        repo = r.get("id", "")
        kind = PIPELINES.get(r.get("pipeline_tag") or "")
        if not kind or _REPACKAGED.search(repo):
            return None
        if self.repo_filter and not re.search(self.repo_filter, repo):
            return None
        if self.exclude and re.search(self.exclude, repo):
            return None
        if (r.get("downloads") or 0) < MIN_DOWNLOADS_30D and (r.get("likes") or 0) < MIN_LIKES:
            return None
        card = r.get("cardData") or {}
        lic = _license(card, r.get("tags") or [])
        meta: dict = {"huggingface_repo": repo}
        if r.get("gated"):
            meta["gated"] = True   # weights require accepting terms on the Hub
        if r.get("createdAt"):
            meta["released"] = r["createdAt"][:10]
        if card.get("base_model"):
            base = card["base_model"]
            meta["base_model"] = base if isinstance(base, list) else [base]
        return SyncModel(
            model_id=repo,
            display_name=_display_name(repo),
            type=kind,
            languages=_languages(card),
            streaming=False,   # self-hosted: streaming depends on the runtime, not the weights
            open_weights={
                "license": lic or "unspecified",
                "url": f"https://huggingface.co/{repo}",
                "commercial_use": commercial_use(lic) if lic else None,
            },
            meta=meta,
            source="api",
        )
