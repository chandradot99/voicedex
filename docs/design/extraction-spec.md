# Docs extraction spec (voice provider registry)

Repo: /Users/chandradot99/Projects/naaviq-voice-providers

You extract one provider's models (and voices, if the syncer parses voices from docs) from its
documentation and write them as JSON into `.sync-cache/` in the repo. A human-reviewed diff follows,
so accuracy beats completeness: **never guess; omit any field the docs don't state.**

## Steps
1. Read `voicedex/sync/<provider>.py`: note every `parse_models_from_docs(...)` / `parse_voices_from_docs(...)`
   call — its `seed_urls`, `model_type` and guidance string. Those define WHAT to extract.
   Also read `voicedex/sync/base.py` (SyncModel / SyncVoice fields) and `CLAUDE.md` "Data conventions".
2. Fetch the seed URLs with WebFetch; follow links (models overview, API reference, pricing page,
   `llms.txt`) as needed. If seed URLs are dead/moved, find the current pages and REPORT the new URLs.
3. Write the cache files (pretty JSON arrays):
   - models: `.sync-cache/<provider_id>_<stt|tts|sts>_models.json` (provider_id as in the syncer, e.g. `amazon-transcribe`)
   - voices (only if the syncer calls parse_voices_from_docs): `.sync-cache/<provider_id>_voices.json`
4. Validate by running: `uv run python scripts/sync.py <provider_id>` (dry-run; never pass --write).
   Fix any validation error it prints. Don't modify any other repo files.

## Model object (SyncModel JSON)
Required: `model_id` (exact string used in API calls), `display_name`, `type` ("stt"|"tts"|"sts").
Optional — include only if stated:
- `languages`: BCP-47 codes (`en`, `en-US`, `hi-IN`). `["*"]` only when docs give a count/"multilingual" without listing.
- `streaming` (bool; true only if usable over a realtime/websocket/streaming API), `is_default` (exactly one per type: newest recommended production model)
- `lifecycle`: "alpha" | "beta" | "ga" (alpha/beta ONLY when labeled Preview/Beta/Experimental/Alpha)
- `description` (one sentence, paraphrased), `eol_date` ("YYYY-MM-DD")
- `sample_rates_hz` (ints), `audio_formats` (lowercase, cross-provider names: mp3, wav, pcm, opus, flac, ogg, mulaw, alaw, aac, webm, m4a … — map raw encodings like pcm_s16le→pcm, ulaw/µ-law→mulaw; put exact encodings in meta)
- `max_text_chars` (TTS, per request), `max_audio_seconds` (STT, per request)
- `capabilities` — ONLY these terms, only if stated for that model:
  STT: word_timestamps, speaker_diarization, punctuation, profanity_filter, custom_vocabulary, language_detection, translation, sentiment, pii_redaction, summarization, topic_detection
  TTS: emotion, voice_cloning, voice_design, ssml, phoneme_input, prosody_control, style_control, multi_speaker
  Anything else → `meta`.
- `regions`: subset of us | eu | asia | global, only if docs state availability by region
- `interfaces`: subset of http | websocket | grpc | webrtc
- `pricing` (only explicit published numbers; non-USD-only providers: `"currency": "INR", "price": n` instead of `price_usd`, never converted): `{"unit": "character|minute|second|word|token|request|hour", "price_usd": n, "as_of": "<today>", "source_url": url, "notes": "plan/qualifiers"}`; differing tiers → `"variants": [{"applies_to": "...", "unit": "...", "price_usd": n}]`. `price_usd` is the price anyone can pay without a subscription commitment (pay-as-you-go / list rate) when one is published; a lower rate that requires buying a monthly or annual plan goes in `variants` with the plan named in `applies_to`, never in `price_usd` (it would show as the "cheapest" price everywhere). Promotions open to every customer are the current price: keep them in `price_usd` and say "promo" plus any end date in `notes`
- `meta`: provider extras. Special keys promoted to fields: `parent_model_id` (family root), `snapshot_date`, `alias_of` (for moving aliases), `batch` (bool: usable via file/batch API).
- Lineage (feeds the provider page "Start here" header; top-level keys or `meta`, only from the vendor's own pages):
  `released_on` — when the model became callable via the API, at the precision published ("2026-04-17" or "2026-04"; a
  waitlist/alpha date doesn't count, a public preview does). `recommended` — `true` only when the docs point new
  integrations to it ("recommended", "use X for …", flagship on the models page), with `recommended_for` = the use case
  they name; `false` when they call it legacy / previous-generation / say to use something else; omit otherwise. Several
  models per type can be recommended (one per use case). `replaces` — ids of this provider's models the docs say it
  succeeds; never inferred from version numbers. Reviewed values survive later syncs (empty = unknown).

**Deprecated models:** INCLUDE models that are deprecated but still callable with an announced future
shutdown date — set `eol_date` to it and `meta.replacement` / `meta.deprecation_notice`. EXCLUDE models
already shut down and models deprecated with no date (merge handles deprecation). Never invent dates. Don't enumerate
models that aren't callable (marketing names without an API id).

## Voice object (SyncVoice JSON)
Required: `voice_id` (exact API string — never append notes/annotations from the docs; those go in `meta`), `display_name`. Optional: `gender` (male|female|neutral),
`category` ("premade"), `languages` (BCP-47), `description`, `preview_url`, `accent` (lowercase, e.g.
american, british, indian), `age`, `use_cases`, `tags`, `compatible_models` (`["*"]` if the voice works with
all of this provider's TTS models; explicit model ids otherwise), `capabilities` (emotion|multilingual_native), `meta`.

## Report back (≤ 300 words)
Files written + counts; URLs used (flag dead/moved seed URLs and the replacements); default choices
with a supporting quote; excluded/deprecated models; anything ambiguous; and whether the provider/product
appears shut down, acquired or pivoted. Paste the dry-run summary lines (the `stt:/tts:/voices:` counts).

## Editorial fields (new providers)
Also write `.sync-cache/<provider_id>_editorial.json` (applied by `scripts/apply_editorial.py`), only with facts
you verified on the provider's own site:
`{"website": url, "description": "2–3 factual sentences: who they are (HQ city/country, founded, parent/acquirer),
what speech products they sell, notable language focus; no marketing adjectives", "access": "self_serve|enterprise|regional|open_weights",
"headquarters": "ISO alpha-2", "regions": [us|eu|asia|global — only where data/inference regions are documented],
"compliance": [soc2|hipaa|gdpr|iso27001|pci_dss — only if the provider states certification/compliance],
"links": {"docs": url, "api_reference": url, "pricing": url, "status": url}}`.
Non-USD providers: keep prices in the published currency (`currency` + `price`). Credit-priced providers: put the
credit rate in `pricing.notes`/`meta`; set a money price only if the provider publishes one per unit.
