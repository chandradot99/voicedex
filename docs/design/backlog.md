# Backlog

Known gaps and follow-ups, newest first. Move items to commits as they're done.

## Data coverage
- **Syncer fixes queued for when keys arrive** (docs already extracted into .sync-cache/):
  smallestai voices endpoint `/lightning-v3.1/get_voices` retires 2026-11-30 → use `/lightning-v3.1-pro/get_voices`;
  fishaudio top-200-by-popularity voice cap causes deprecation churn → fetch a stable set;
  murf has a beta STT product (finch_*) the syncer doesn't request; speechify docs moved to docs.speechify.ai (old seeds redirect); typecast docs.typecast.ai is dead (use typecast.ai/docs); groq `_AUDIO_MODEL_META` still lists the shut-down PlayAI models; AI guidance in every remaining syncer hardcodes model ids — replace with generic guidance + current seed URLs (in each agent report, summarised in the cache-commit messages).
- **Amazon Polly** — needs an AWS account + IAM user with `polly:DescribeVoices` (deferred 2026-11-16: AWS sign-up issues).
- **Speechmatics TTS** (preview): 4 voices, no model id, $0.011/1k chars — add as tts once it has a stable model id.
- **Rime STT and "Prism" STS** — syncer is TTS-only.
- **Deepgram Flux** (conversational STT) and **Deepgram capabilities** — not in `/v1/models`; needs a docs pass (Deepgram → mixed).
- **ElevenLabs community voice library** (thousands of shared voices) — only premade voices today; consider a separate `community` category.
- **AssemblyAI** dashboard-only voice catalog ("thousands") — only the 34 documented starter voices.
- **provider.json editorial fields** (website, description, regions, compliance, links) — empty for every provider; fill from a verified research pass.
- **Missing providers** — Soniox, Google Gemini TTS/Live, NVIDIA Riva/Parakeet, Kyutai, xAI, Qwen, Microsoft MAI-Voice, open-weight models (Kokoro, Orpheus, Chatterbox…) and their hosts. Needs a verified research pass.

## Schema
- **Pricing currency** — `pricing` is USD-only; Gladia (EUR) and Sarvam (INR) prices sit in `meta.pricing_<ccy>`. Add `currency` (ISO 4217) with `price` + keep `price_usd` for USD rows.
- **Per-locale voice accents** — Cartesia/ElevenLabs expose accent per locale (in `meta.locale_accents` for Cartesia).
- **Plan-dependent pricing** — prices often differ per plan (Rime Scale, Cartesia Scale); `variants` covers it loosely.

## Product
- Homepage + catalog UI, project rename, npm/PyPI packages, changelog/RSS of data changes, benchmarks, Pro tier.
- Deploy v2 (needs user sign-off: Railway config change, Neon can be retired).
