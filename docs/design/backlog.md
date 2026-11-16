# Backlog

Known gaps and follow-ups, newest first. Move items to commits as they're done.

## Data coverage
- **Syncer fixes queued for when keys arrive** (docs already extracted into .sync-cache/):
  smallestai voices endpoint `/lightning-v3.1/get_voices` retires 2026-11-30 → use `/lightning-v3.1-pro/get_voices`;
  fishaudio top-200-by-popularity voice cap causes deprecation churn → fetch a stable set;
  murf has a beta STT product (finch_*) the syncer doesn't request; speechify docs moved to docs.speechify.ai (old seeds redirect); typecast docs.typecast.ai is dead (use typecast.ai/docs); groq `_AUDIO_MODEL_META` still lists the shut-down PlayAI models; AI guidance in every remaining syncer hardcodes model ids — replace with generic guidance + current seed URLs (in each agent report, summarised in the cache-commit messages).
- **Mistral voices** — 20 preset TTS voices need a paid-plan key (skipped 2026-11-16); models are synced from docs.
- **WellSaid voices** — avatar listing needs a paid-plan key (skipped 2026-11-16); models are synced from docs.
- **Amazon Polly** — needs an AWS account + IAM user with `polly:DescribeVoices` (deferred 2026-11-16: AWS sign-up issues).
- **Speechmatics TTS** (preview): 4 voices, no model id, $0.011/1k chars — add as tts once it has a stable model id.
- **Rime STT and "Prism" STS** — syncer is TTS-only.
- **ElevenLabs community voice library** (thousands of shared voices) — only premade voices today; consider a separate `community` category.
- **AssemblyAI** dashboard-only voice catalog ("thousands") — only the 34 documented starter voices.
- **provider.json editorial fields** (website, description, regions, compliance, links) — empty for every provider; fill from a verified research pass.
- **Missing providers** (researched 2026-11-16; Pipecat/LiveKit integration lists + vendor docs):
  - ADD, API-syncable: **Soniox** (`GET /v1/models`; stt-*-v5 EOL 2026-12-15, v4→v5 aliases), **xAI** (STT/TTS/realtime; `GET /v1/tts/voices`; models docs), **Gradium** (Kyutai spin-off; `GET /api/voices/`), **Alibaba Model Studio intl** (`GET /api/v1/models` filters ASR/TTS/realtime, returns prices + retirement dates).
  - ADD, docs-based: **Meta Muse Voice Transcribe** (STT), **Async** (TTS + ASR), **StepFun** (TTS/ASR/realtime, USD prices), **BytePlus Seed Speech** (JS-rendered docs).
  - MAYBE: Zoom Scribe, Ultravox (now Inworld; sts only), Respeecher, Bland TTS, Deepdub, Boson Higgs, Gnani (if self-serve), AmiVoice (JPY), Naver CLOVA, Tencent, iFLYTEK, Reverie, NVIDIA (open-weights/self-host).
  - Retired-provider records worth adding: PlayHT (Meta, 2025-12-31), Coqui (2024), Supertone (liquidated 2026-07).
  - Gaps in existing providers: Azure MAI-Transcribe, Gemini Live / Azure Voice Live / Amazon Nova Sonic (sts).
  - Model hosts (Together, fal, DeepInfra): not first-class providers — later a "hosted by" dimension on open-weight models.

## Schema
- **Pricing currency** — `pricing` is USD-only; Gladia (EUR) and Sarvam (INR) prices sit in `meta.pricing_<ccy>`. Add `currency` (ISO 4217) with `price` + keep `price_usd` for USD rows.
- **Per-locale voice accents** — Cartesia/ElevenLabs expose accent per locale (in `meta.locale_accents` for Cartesia).
- **Plan-dependent pricing** — prices often differ per plan (Rime Scale, Cartesia Scale); `variants` covers it loosely.


- **Async voices** — stock library only via `POST api.async.com/voices` (X-Api-Key; filter out `my_voice`). Needs ASYNC_API_KEY; models are docs-synced.


- **Alibaba Jan 19, 2027 retirement batch** — notice id=2217 (alibabacloud.com/notice/detail?id=2217) is JS-rendered and wasn't readable headless; check whether any synced speech models are in it and set `eol_date`.

- **Unpriced models (56, 2026-11-16)** — no published per-unit price: CAMB, WellSaid (plan-only), Neuphonic (contact sales),
  Gradium (credits; in meta), IBM TTS ("as low as"), Azure MAI-Voice/HD Flash/Omni, Deepgram Nova-1/medical/whisper sizes,
  Google usm/experimental/Chirp-HD TTS, MiniMax speech-01, Rime mist/mistv2, StepFun realtime preview (free until
  2026-11-23, then stepaudio-3-realtime $0.125/session-min). Re-check with the pricing spec periodically.

- **Deepgram Flux** (conversational STT) not yet in the catalog; Deepgram features came from docs via apply_docs (2026-11-16).

## Product
- Homepage + catalog UI, project rename, npm/PyPI packages, changelog/RSS of data changes, benchmarks, Pro tier.
- Deploy v2 (needs user sign-off: Railway config change, Neon can be retired).
