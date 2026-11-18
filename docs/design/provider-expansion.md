# Provider expansion plan

Researched 2026-11-18. Five parallel web-research passes covered: US/CA/EU plus on-device; China, Taiwan, Japan and Korea; South and Southeast Asia;
MENA, Africa, LatAm and CIS; open weights plus inference hosts. Today the catalog has 36 live and 7 retired providers.
**Goal:** about 95 providers covering the biggest, the smallest and the regional, without lowering the data bar.

> Facts marked **(verify)** came from aggregators or search snippets, not the vendor's own page. Re-check them during
> extraction. Never write a price that can't be traced to a vendor page (CLAUDE.md: "Never guess numbers").

## 1. Inclusion policy

A provider gets an entry if it **owns its speech models** (STT, TTS or STS) and exposes them through an API or SDK a developer can obtain.

| Tier | Bar | Catalog treatment |
|---|---|---|
| Self-serve | Sign up, get a key, pay per unit or by credit | Normal entry |
| Enterprise | Public API docs, sales-led access or pricing | Entry with `access: enterprise`; models without pricing are fine |
| Regional registration | Needs a local ID, entity or phone (CN real-name, RU entity, India Bhashini integrator) | Entry with `access: regional`; usually docs-synced |
| Open weights | Weights on HF/GitHub with an exact licence, **plus** one of: ≥250k downloads or ≥1k likes on a current repo, top-10 on Open ASR Leaderboard or a TTS Arena, or served per-unit by ≥2 hosts | Org entry whose models carry `open_weights`; re-check quarterly |
| Retired | Shut down, or stopped selling to new customers | `status: deprecated` record, never deleted |

**Excluded:** consumer apps with no API; orchestrators and resellers (Vapi, Retell, Twilio, Vonage, AudioStack,
Uberduck, CoRover, contact-centre suites); inference hosts as providers (they get a separate "hosted by" dimension, §6).

## 2. Schema and pipeline prerequisites (do first, small)

1. **`provider.access`**: `self_serve | enterprise | regional`, an editorial field. It shows on the provider page and can be used as a filter.
2. **`open_weights.commercial_use: bool`**: licences like OpenMDW, CPML, CC-BY-NC and the "research" licences are
   opaque to readers, and this is the first thing people filter on.
3. **Retired seller ≠ dead weights.** Hume (TADA) and Resemble (Chatterbox, 2.5M downloads) are retired as API sellers,
   but their open weights are alive. Allow active `open_weights` models under a `status: deprecated` provider. The sync
   skip stays; these models come from a small open-weights syncer.
4. **Region-dependent prices** (Alibaba Beijing vs Singapore, Tencent CN vs intl): use pricing `variants` keyed by region.
   No new field.
5. **Credit pricing** (Munsit, iApp, Gradium): record the published credit rate in `pricing.notes` or `meta`. Fill
   `price`/`price_usd` only when the vendor publishes a per-unit money price; never derive one from plan maths.
6. **An open-weights syncer** reading the Hugging Face API (`/api/models?author=…`) for downloads, likes, licence and the
   `pipeline_tag`. This is a real API, so no docs pass is needed.

## 3. Wave 0: gaps in providers we already list (highest value per hour)

| Provider | Missing | Source |
|---|---|---|
| google-cloud | **sts** `gemini-3.8-live`, `gemini-3.8-live-extended-thinking` (2026-09-15); `gemini-live-2.5-flash-native-audio` (eol **2026-12-13**: include it with `eol_date`, it drops out after that date); **stt** `gemini-3.5-transcribe-live` | blog.google Gemini audio post; Vertex Live API docs |
| deepgram | `flux-general-en`, `flux-general-multi` (conversational STT; prices **verify**) | deepgram.com/pricing |
| azure | stt MAI-Transcribe-2 (promo $0.10/h until 2026-12-31), MAI-Transcribe-2-Streaming (preview), MAI-Transcribe-1.5; **sts** Voice Live (Pro/Standard/Lite, per 1M tokens) | microsoft.ai/news/mai-transcribe-2 |
| **amazon-nova** (new id; Polly and Transcribe are separate ids) | sts `amazon.nova-2-sonic-v1:0` (EOL ≥ 2026-12-02 **verify**), Nova 2.5 Sonic (GA 2026-10-05); check that Nova Sonic v1 is gone | Bedrock model cards |
| inworld | **Ultravox** sts (acquired 2026-09-30; $0.05/min; signup open). Add it as an Inworld sts model and record the acquisition in the description | ultravox.ai/pricing |
| amazon-polly | Still unsynced (blocked on the AWS account) | backlog |
| alibaba | Mainland-only models (cosyvoice-v3.5-plus/flash, Beijing) as region variants in CNY | help.aliyun.com (**verify**) |
| rime | Check whether "Arcana" (Sinhala, with Dialog Axiata, 2026-05) appears in the sync | dialog.lk |

Already covered, no action: Groq serves Orpheus (en and ar-SA), and Gradium is the commercial arm of Kyutai.

## 4. New providers, by wave

Columns: **sync** is the expected source (api = list endpoint found, docs = docs extraction) · **ccy** is the published pricing currency (— = none published).

### Wave 1: major clouds and labs (global plus regional heavyweights)

| id | Name | HQ | Types | Access | sync | ccy | Notes |
|---|---|---|---|---|---|---|---|
| nvidia | NVIDIA (Riva/NIM, build.nvidia.com) | US | stt, tts | self_serve trial / enterprise | docs + HF | — | Nemotron 3.5 Transcribe (#1 Open ASR), Parakeet v2/v3, Canary, Magpie TTS; also open weights |
| tencent | Tencent Cloud ASR/TTS | CN | stt, tts | self_serve (intl) | docs | USD + CNY | intl standard TTS $0.125, premium $0.185 per 10k chars; CN LLM TTS ¥2.5/万字符 |
| iflytek | iFLYTEK Open Platform (global.xfyun.cn) | CN | stt, tts | self_serve (global) | docs | USD | Priced per **request** ($1.40/1k calls) |
| volcengine | Volcengine Doubao Speech | CN | stt, tts, sts | regional (CN real-name) | docs | CNY | Separate catalog from BytePlus; TTS 2.0 ¥3/万字符, ASR 2.0 ¥1/h, realtime per token |
| naver-clova | Naver Cloud CLOVA Speech/Voice | KR | stt, tts | self_serve | docs | KRW (**verify**) | Korea's main cloud speech stack; English docs |
| yandex | Yandex SpeechKit | RU | stt, tts, sts | self_serve (USD via Serbia/Dubai entities) | docs | USD | STT ~$0.0053/min, TTS v1 $11/1M chars; ru, kk, uz. Note the sanctions/compliance context in the description |
| zhipu | Zhipu / Z.ai | CN | stt, tts, sts? | self_serve (Z.ai intl) | docs | USD | GLM-ASR-2512 $0.03/1M tokens; GLM-TTS; GLM-Realtime (**verify**) |
| xiaomi | Xiaomi MiMo | CN | stt, tts | self_serve | docs | USD + CNY | ASR $0.074/h; TTS free for now (clone and design variants) |
| cohere | Cohere Transcribe | CA | stt | self_serve? | docs + HF | (**verify**) | cohere-transcribe-03-2026, Apache-2.0; check that it is on the paid API |

### Wave 2: self-serve independents with prices (US/EU, plus on-device)

| id | Name | HQ | Types | sync | Pricing / note |
|---|---|---|---|---|---|
| bosonai | Boson AI (Higgs) | US | tts, sts, stt | docs | Free preview; Higgs TTS 3, Higgs Realtime |
| phonic | Phonic | US | sts | docs | ~$0.07/min (**verify**) |
| bland | Bland Speech (BTTS v3) | US | tts | api (List Voices) | Per character, rate unpublished |
| zoom | Zoom AI Services: Scribe | US | stt | docs | Batch $0.15/h, Fast $0.20/h |
| modulate | Modulate | US | stt | docs | Published hourly rates; figures look implausibly low (**verify**) |
| voicegain | Voicegain | US | stt | docs | $0.0002/s, 6 s minimum |
| picovoice | Picovoice (Leopard, Cheetah, Orca) | CA | stt, tts (on-device) | docs | Licence pricing, not per-unit; `interfaces` = on-device (add the term) |
| kugelaudio | KugelAudio | DE | tts | docs | EUR per minute, sources conflict (**verify**) |
| vatis | Vatis Tech | RO | stt | docs | €0.22/h async (**verify**: the ES page says €0.17) |
| shunya | Shunya Labs (Zero STT) | IN/US | stt | docs | $0.0039–0.0050/min, 200+ languages |
| zyphra | Zyphra (Zonos) | US | tts | docs + HF | API plus Apache-2.0 ZONOS3 weights |

### Wave 3: regional language specialists (the coverage moat)

| id | Name | Region | Types | sync | ccy | Languages added |
|---|---|---|---|---|---|---|
| gnani | Gnani.ai (Vachana) | IN | stt, tts | docs | — | 10 Indic; enterprise pricing |
| upliftai | Uplift AI (Orator, Scribe) | PK | tts, stt | docs | — | **Urdu**, Punjabi, Balochi |
| navana | Navana.ai (Bodhi) | IN | tts (stt invite-only) | docs | INR (₹12/10k chars) | 9 Indic |
| dubverse | Dubverse | IN | tts | docs | USD + INR | Indic |
| reverie | Reverie (RevUp) | IN | stt, tts | docs | — | 11–12 Indic + **Nepali** |
| bhashini | Bhashini (MeitY) | IN govt | stt, tts | **api** (pipeline search) | — | 22 scheduled languages; PoC-only terms → `access: regional` |
| fptai | FPT.AI | VN | tts, stt | docs | VND packs | **Vietnamese** |
| iapp | iApp Technology (Chinda) | TH | stt, tts | docs | THB credits | **Thai** |
| botnoi | Botnoi Voice | TH | tts | docs | (**verify**) | Thai, 525 voices |
| munsit | Munsit (CNTXT) | AE | stt, tts | **api** (`/api/v1/voices`, models API) | USD credits | **Arabic, 25+ dialects** |
| spitch | Spitch | NG | stt, tts | docs / SDK | — | **Yoruba, Hausa, Igbo, Amharic** |
| sunbird | Sunbird AI | UG | stt, tts | docs | — | **51 African languages** (STT) |
| lelapa | Lelapa AI (Vulavula) | ZA | stt | docs | USD per **request** | isiZulu, Sesotho, Afrikaans |
| aisha | Aisha AI | UZ | tts, stt | docs | — | **Uzbek** |
| amivoice | AmiVoice (Advanced Media) | JP | stt | docs | JPY (**verify**) | Japan's leading STT |
| coefont | CoeFont | JP | tts | **api** (`GET /coefonts/pro`) | JPY | Japanese |
| rtzr | ReturnZero (RTZR) | KR | stt | docs | KRW (₩1,000/h) | Korean |

### Wave 4: enterprise-flagged (public docs, sales-led)

Deepdub (US/IL tts), aiOla Jargonic (US/IL stt), Intron Sahara (NG stt, 57 languages), Sestek Knovvu (TR stt/tts, the only
Turkish model owner found), CPqD (BR pt-BR stt/tts, the only LatAm model owner found), Intella (EG/KSA Arabic stt), Huawei Cloud
SIS (CN), ReadSpeaker (SE/NL tts), Acapela (BE tts), CereProc (UK tts), Phonexia (CZ stt), Vocapia (FR stt), Tilde (LV, Baltic
stt/tts), Verbio (ES), Respeecher (US/UA voice conversion), Khaya AI (GH, Twi/Ewe/Ga).

### Wave 5: open-weights orgs (after the prerequisites in §2)

New orgs: **hexgrad** (Kokoro, 13M downloads), **kyutai** (Moshi, STT, TTS, pocket-tts; CC-BY-4.0), **openbmb** (VoxCPM2),
**k2-fsa** (OmniVoice, 600+ languages, non-commercial), **ai4bharat** (IndicConformer, Indic Parler-TTS, IndicF5),
**canopylabs** (Orpheus), **sesame** (CSM-1B), **microsoft** (VibeVoice-ASR/TTS, Phi-4-multimodal; a separate org entry, because Azure is a product
and VibeVoice isn't sold there), **liquidai** (LFM3-Audio), **swivid** (F5-TTS, non-commercial).
Attach `open_weights` to existing providers: openai (Whisper), alibaba (Qwen3-ASR/TTS, CosyVoice, SenseVoice), mistral
(Voxtral STT Apache-2.0; Voxtral TTS CC-BY-NC), fishaudio (s2-pro, research licence), meta (omniASR, Seamless, MMS),
ibm (Granite Speech 5.0, #3 Open ASR), stepfun (Step-Audio 2), gradium (phonon), neuphonic (NeuTTS Air).
Retired orgs with live weights: coqui (XTTS-v2, CPML), resemble (Chatterbox), humeai (TADA).

### Retired records to add

| id | Name | retired_on | Evidence |
|---|---|---|---|
| sber-salutespeech | Sber SaluteSpeech | 2026-07-15 | developers.sber.ru tariff pages: sales of new packages stopped |
| nijivoice | Nijivoice (JP) | 2026-02-04 | Service and API shut down (**verify** the source page) |
| replica | Replica Studios (AU) | 2025-06-30 | Shut down |
| symbl | Symbl.ai | — (acquired by Invoca 2025-05-28; decommission date unknown) | Developer platform gone |

## 5. Watchlist (re-check next quarter; not enough evidence yet)

Baidu AI Cloud (site unreachable), Krutrim (no public prices), Viettel AI, Vbee, Zalo AI, Prosa.ai (ID), Lahajati (docs 404),
Ramsa (AED), Kotoba (JA↔EN STS; only via fal today), Aivis Cloud (JP), Narakeet (are the voices its own?), Argmax WhisperKit,
Fireworks streaming ASR, Soniqo, Sanas, Krisp translation, T-Bank VoiceKit, Muxlisa (UZ), AyaSpeech (GH), NKENNEAi
(Swahili), Devnagri, ConvoZen, GigaTech (BD), DeepBrain AI, Speechtext.ai, Lingvanex, NeuralSpace.
**Coverage holes with no viable vendor found:** Philippines, Nepal (Reverie covers ne), Indonesia (Prosa only),
Persian (Iran is sanctioned; no API), LatAm independents, Mongolia (not searched).

## 6. Later: "hosted by" dimension

Inference hosts serve both open weights **and resold closed models** (Together → Cartesia, Cloudflare → Deepgram, fal/Replicate
→ ElevenLabs, MiniMax, Gemini, Inworld). Model it as `hosted_by[] {host, model_ref, pricing}` keyed by HF repo id or provider
model id. Feeds, in order: **DeepInfra** (`GET api.deepinfra.com/models/list`, public, with per-char and per-second prices),
**fal** (`/v1/models/pricing`, needs a key), **Together** (`/v1/models`), then Cloudflare, Groq and SiliconFlow from docs.

## 7. Execution notes

- Each provider follows CLAUDE.md "Adding a provider": syncer, registry, `--write`, editorial fields, validate, and a parsing test.
  Docs-based ones reuse `DocsOnlySyncer` (one small file each). Seed URLs are listed in the research tables above.
- **API keys and sign-ups are the user's call** (accounts, KYC, CN real-name). Without a key, sync docs-only and add the
  API path when a key arrives. Volcengine and CN-side Tencent/Baidu probably stay docs-only.
- Batch by wave, one commit per provider so each `git diff data/<id>` is reviewable.
- Expected end state: ~36 → ~95 providers, with Arabic dialects, Urdu, Vietnamese, Thai, Uzbek, Yoruba/Hausa/Igbo, Luganda and Japanese/Korean
  specialists covered by native vendors, not only by hyperscalers.

## Status — 2026-11-18 (branch `providers/expansion`)

Done: §2 prerequisites (access, headquarters, commercial_use, retired-with-weights, HF open-weights syncer,
apply_editorial); Wave 0 (Google Gemini Live + 3.5 Transcribe, Deepgram Flux, Azure MAI-Transcribe + Voice Live,
Amazon Nova Sonic, Inworld/Ultravox); Waves 1–3 complete; Wave 4: Deepdub, Intron, Sestek, Huawei Cloud, Khaya,
ReadSpeaker, Acapela, CereProc, Respeecher, Phonexia; Wave 5: 10 open-weights orgs + weights of Resemble/Hume/Coqui;
retired records: Sber SaluteSpeech, Nijivoice, Replica, Symbl, Dubverse, Verbio. Editorial fields filled for every
live provider. Catalog: 92 live + 13 retired providers, 684 active models, 14,766 voices.

Dropped after verification (moved to watchlist): Vocapia (API docs behind a request form), Tilde (system ids need a
key: `GET /asr/systems`, `/tts/systems` — add an API syncer once a key exists), CPqD (docs return 401; on-prem only),
Intella (no public docs), aiOla (Jargonic API waitlist-only; console domain gone).

Upgrade candidates (public keyless list endpoints found during extraction): Bland `GET api.bland.ai/v2/models`,
Zyphra `GET api.zyphracloud.com/api/v1/models` (with prices), Sestek `GET <region>/v1/speech/dictation/models`.
Key-gated voice lists that would add voices: CoeFont, KugelAudio, Munsit, Zyphra, Respeecher, Bhashini pipelines.
