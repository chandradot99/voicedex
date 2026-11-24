# Voicedex

Open catalog of voice AI providers — STT/TTS/speech-to-speech models, voices, languages, capabilities,
pricing, regions. **Data lives in git (`data/`), served by a read-only FastAPI app** with a server-rendered
catalog UI. Domain: `voicedex.dev`. Python package: `voicedex` (formerly `naaviq`; public UUIDv5 ids are
unaffected — the namespace in `voicedex/catalog/store.py` is a fixed constant and must never change).

Architecture decisions: `docs/design/v2-architecture.md` (D1–D7). Read it before structural changes.

## How it works

```
provider APIs / docs ──▶ voicedex/sync/<provider>.py ──▶ SyncResult
                                                         │  scripts/sync.py: validate → merge → guard → diff
                                                         ▼
                                    data/<provider>/{provider,models,voices}.json   (git = database)
                                                         │  commit / PR = review step; deploy = publish
                                                         ▼
                                    voicedex/main.py loads data/ into memory → /v1 REST API + /v1/catalog.json
```

- **No database.** The API loads `data/` at startup (`voicedex/catalog/store.py`). Deploying a commit publishes its data.
- **History/audit/rollback = git.** Price history: `git log -p data/*/models.json`.
- Hosting: Google Cloud Run (`voicedex-prod`, us-central1) behind Cloudflare, serving the Dockerfile image (copies `data/`). CI (`.github/workflows/ci.yml`): ruff → `scripts/validate.py` → pytest, then on `main` the `deploy` job builds, pushes and deploys (keyless WIF; setup in `docs/deploy.md`). Scale-to-zero; Cloud Scheduler job `voicedex-keepwarm` pings `/health` every 5 min to avoid most cold starts. `TRUST_CF_CONNECTING_IP=true` (rate-limit key); `SITE_URL` drives canonical/sitemap/share URLs.

## Layout

```
voicedex/
  main.py            — app, catalog loading, ETag/Cache-Control middleware
  mcp_server.py      — remote MCP server at /mcp (Streamable HTTP, stateless, read-only tools over the Catalog);
                       GET /mcp serves the setup page (SSE-only GETs get 405)
  config.py          — provider API keys, DATA_DIR, rate limit
  limiter.py         — slowapi; keys on right-most X-Forwarded-For (proxy-appended)
  schemas.py         — API response models (v1-compatible field names + v2 additions)
  catalog/
    schema.py        — THE contract: Provider/Model/Voice + controlled vocabularies (Pydantic)
    files.py         — deterministic read/write of data/<provider>/*.json
    merge.py         — SyncResult → records; merge rules; shrink guard; diff report
    store.py         — in-memory Catalog, stable UUIDv5 ids, language matching
  web/               — server-rendered pages (Jinja + one site.css/site.js, no build). Design system (tokens at the
                       top of site.css), benchmarked against premium dark products (Linear, OpenRouter, Raycast):
                       "Ink" dark = warm near-black #0b0a08 (OKLCH L 0.145, hue 80, matched to the amber), panels step
                       up / wells step down, borders translucent; text 18:1 / 11.7:1 / muted 7.4:1. Light "Paper"
                       #fdfcf9. Type: Instrument Sans (variable width; tables/rails at --narrow 94%) + Geist Mono ONLY
                       for things you copy (ids, code, keys); numbers use tabular figures (.mono = tabular-nums).
                       Scale 12/13/14/16/20/28/40px (+60px home headline), nothing below 12px; labels sentence case.
                       Radius 6px controls/cards, 4px badges/logos; 1px rules between table rows. Amber (#f5a524) =
                       selected / "this one" / focus only; coral only for shutdowns/errors; no gradients, colour-coded
                       types or 01/02/03 numbering on non-sequences. Inline 16px stroke icons in templates/_icons.html.
                       Provider logos: static/logos/<id>.png (64px opaque tiles from scripts/fetch_logos.py, lettered
                       tile fallback via cells.logo). Home hero: the "provider equaliser" (site.js [data-hero-ring], canvas): one bar per provider, length ∝ log(models), level-meter wobble, an amber sweep naming widely used providers; static under reduced motion. The price spectrum follows it.
                       og.png comes from scripts/make_og_image.py. Asset URLs carry a content hash (?v=).
                       Dark is the default for everyone; light is opt-in via the header toggle (localStorage "theme").
                       SEO: filtered /models?… canonicalizes to /models, so indexable landing pages are generated from
                       data (views.landing_pages): /{speech-to-text|text-to-speech|speech-to-speech}[/<language>|/<feature>
                       |/open-source (grouped by licence tier)|/realtime (WebSocket/WebRTC)], only when ≥ MIN_LANDING_MODELS match.
                       views.TASKS = "start from what you're building" cards pointing at those pages (home + hubs).
                       Cost calculator (views.USAGE/monthly_cost, _usage.html, site.js [data-usage]/[data-rate]): "Per month"
                       column on single-type model tables + a block on model pages; server-rendered at a default usage
                       (TTS 10M chars, STT/STS 100 h), live in JS, ?usage= without JS. List price, before free tiers.
                       /reports/speech-ai-pricing (views.pricing_report): recomputed from data; findings are written only when
                       the numbers support them; ranges = 5th–95th percentile (≥20 prices), medians need ≥ MIN_GROUP models;
                       never names a single cheapest model (extremes can be plan-gated - see the pricing rule).
                       Landing and provider pages carry a data-generated FAQ (views.landing_faq/provider_faq) + FAQPage JSON-LD. Also JSON-LD (Dataset, BreadcrumbList),
                       sitemap <lastmod>, /llms.txt, and a 301 for trailing slashes (main.py).
                       /compare/<a>-vs-<b>: provider pairs from views.COMPARE_PROVIDERS (editorial list) that share a
                       model type; alphabetical slug, reverse order 301s. /changes + /changes.xml (Atom): web/changes.py
                       replays git history of data/ (CI bakes data/.changes.json; local dev reads git).
                       /providers: sortable index (type filter; filtered views canonicalize to /providers); home shows
                       only the widely used ones (COMPARE_PROVIDERS). /models and /voices are "workbench" pages
                       (.wrap-wide, up to 1600px): a filter rail with live counts per option (routes._filter_models /
                       _filter_voices with skip=…), repeatable ?capability= (AND), radios for type/status/gender, and a
                       compact-rows toggle (localStorage "density", applied in <head>). /models default order =
                       views.default_model_order (recommended → default → widely used providers); also ?sort=price|newest|name.
                       /models paginates at MODELS_PER_PAGE (100); price sort groups comparable USD → other currency/unit
                       → unpriced. Display names show under ids only when views.name_adds. Shared table cells (price
                       amount + unit, features count) live in templates/_cells.html.
                       /alternatives/<provider>: COMPARE_PROVIDERS + every retired provider; active providers of the same
                       type, widely used first, then shared features (only if the subject lists ≥3), then price.
  routers/           — providers.py (/v1/providers/...), catalog.py (/v1/models, /v1/voices, /v1/catalog.json), _filters.py
  sync/
    base.py          — SyncModel / SyncVoice / SyncResult dataclasses + ProviderSyncer
    registry.py      — every provider registered once (id, display name, seeded type, syncer path)
    ai_parser.py     — agentic docs extractor (only on cache miss with ANTHROPIC_API_KEY)
    docs_only.py     — DocsOnlySyncer base for providers with no list API (declare seed URLs + guidance)
    cache.py         — .sync-cache/ handshake for Claude Code extraction
    language.py      — BCP-47 normalization
    <provider>.py    — one syncer per provider
data/<provider>/     — the catalog (generated by sync; provider.json editorial fields are hand-edited)
schema/*.schema.json — generated JSON Schema (scripts/validate.py --schema)
scripts/sync.py      — sync providers into data/ (dry-run default, --write)
scripts/validate.py  — validate data/ + cross-record rules + canonical formatting; CI gate
scripts/catalog_health.py — what's stale/broken/due (syncs, shutdown dates, prices, discovery; --samples)
scripts/check_previews.py — audit every voice-sample link
scripts/fetch_logos.py   — provider logos from their own sites (`uv run --with pillow …`; --report, --force <ids>)
.claude/skills/catalog-refresh/ — `/catalog-refresh [freshness|discover|all|<ids>]`: maintenance run in Claude Code
```

## Skills (Claude Code, `.claude/skills/`)

Project skills run inside Claude Code on the user's subscription — never via the Anthropic API.

| Skill | Use | What it does |
|---|---|---|
| `/catalog-refresh` | routine maintenance (default mode `freshness`) | Runs `scripts/catalog_health.py --samples`, then re-syncs what's due in priority order (shutdown date passed → dead samples → near shutdowns → stale api/mixed → stale docs, ≤ ~10 docs re-extractions per run via subagents), validates, one commit per provider on `refresh/<date>`, summary. |
| `/catalog-refresh discover` | new providers (due every 90 days; `Last discovery pass:` in provider-expansion.md §5) | 4 parallel research subagents (US/EU + clouds, East/SE Asia, India/MENA/Africa/LatAm/CIS, HF open weights + news) against §1 policy; adds qualifying providers, updates the watchlist and the last-pass date. |
| `/catalog-refresh all` | both of the above | |
| `/catalog-refresh <id> …` | refresh specific providers | Re-sync (API) or re-extract (docs) just those. |

Rules baked into the skill: work on a branch and **never merge/push main without the user's OK** (push = deploy);
verify shutdown dates on the vendor's own page; investigate guard refusals before `--allow-shrink`; prices only from
vendor pages. Health thresholds live in `scripts/catalog_health.py` (`STALE_DAYS`, `EOL_SOON_DAYS`,
`PRICING_STALE_DAYS`, `DISCOVERY_EVERY_DAYS`); run it directly any time for a quick report.

## Syncing (the main workflow)

```bash
uv run python scripts/sync.py deepgram            # dry-run: fetch, merge, print per-field diff
uv run python scripts/sync.py deepgram --write    # write data/deepgram/*.json, clear its .sync-cache
uv run python scripts/sync.py --reuse-docs --write   # refresh API-sourced data only; reuse reviewed
                                                  # docs-extracted records from data/ (no docs pass)
uv run python scripts/validate.py                 # always before committing
uv run python scripts/validate.py --fix --schema  # after schema normalization changes: rewrite files canonically
git diff data/deepgram                            # review, then commit
```

Commit messages feed the public changelog (/changes): a commit that **corrects our own data** (not an upstream
change) must include `[skip changes]` in its subject, or it shows up as e.g. "Price changed".

**Never use `ANTHROPIC_API_KEY`.** For `docs`/`mixed` providers, Claude Code reads the docs itself and writes
`.sync-cache/{provider}_{stt|tts|sts}_models.json` / `{provider}_voices.json` (JSON matching SyncModel/SyncVoice
fields), then runs sync. Cache always takes precedence over the API path; it's deleted after `--write`.

Merge rules (`voicedex/catalog/merge.py`):
- new → `first_seen`/`updated_at` = today; unchanged → untouched (no date churn); changed → `updated_at` = today
- incoming `None`/`[]` = unknown → existing value is kept (a docs page omitting pricing never erases it)
- missing upstream → kept and marked deprecated (`lifecycle=deprecated` + `deprecated_at`, `is_default=false`); reappears → revived
- **guard**: refuses if upstream returns nothing for a non-empty section, or would deprecate >25% of ≥4 active records. Investigate first; `--allow-shrink` overrides.
- rejects duplicate ids, >1 default per type, unknown capability terms; drops wrong-modality capabilities

Provider API keys go in `.env` (see `.env.example`). Google STT additionally uses Application Default
Credentials (`gcloud auth application-default login` + `GOOGLE_CLOUD_PROJECT`) for the Speech-to-Text v2
Locations API, which rejects API keys. If `GOOGLE_CLOUD_PROJECT` is set and the login is missing/expired, the
Google sync **fails loudly** (`GoogleAuthExpired`, with the re-login commands) — it never silently degrades. Fix:
`gcloud auth application-default login`. With `GOOGLE_CLOUD_PROJECT` unset (contributors), STT is docs-only.
`scripts/sync.py` ends with a `✗ FAILED: <providers>` line and exit code 1 whenever any provider failed. Naming convention for keys in provider dashboards: `voicedex-sync` (keys created before the rename are named `voice-registry-sync`; no need to recreate them).

## Data conventions

- **Languages**: BCP-47 with uppercase region (`en-US`, `hi-IN`); `"*"` = supports many/unenumerated. Always `normalize_languages()`. API `language=en` matches `en-*`; `language=en-US` also matches bare `en`; `*` always matches.
- **compatible_models** (voices): `["*"]` = all of the provider's models; explicit ids otherwise; `[]` = unknown (never matches a model filter — avoid).
- **regions** (models): `us | eu | asia | global`; `[]` = unknown; `?region=x` matches `x` or `global`. Never guess `global`.
- **lifecycle**: syncers emit `alpha | beta | ga` only (label alpha/beta only when docs say Preview/Beta/Experimental). `deprecated` is set by merge.
- **Deprecation policy**: a model the provider has deprecated but that is **still callable with an announced shutdown date** stays in, with `eol_date` = that date and `meta.replacement`/`meta.deprecation_notice`. Exclude models already shut down, and models deprecated with no date (merge then marks them deprecated). When the date passes, the next sync drops them. Same for voices of retired models. Never invent an `eol_date`.
- **Pricing currency**: `price_usd` for USD. Providers that publish only another currency use `currency` (ISO 4217) +
  `price` (variants: `price`), never converted — e.g. Gladia EUR, Sarvam INR. The UI shows them as published and
  sorts only USD prices. Prices for API-synced providers come from a docs pass: write
  `.sync-cache/<id>_docs.json` and run `scripts/apply_docs.py <id> --write` (a later sync never erases them). The same
  file can carry `capabilities` (+ `capability_notes`) for providers whose API doesn't expose feature support.
- **capabilities** — controlled vocab, enforced on write (`voicedex/catalog/schema.py`). STT: word_timestamps, speaker_diarization, punctuation, profanity_filter, custom_vocabulary, language_detection, translation, sentiment, pii_redaction, summarization, topic_detection. TTS: emotion, voice_cloning, voice_design, ssml, phoneme_input, prosody_control, style_control, multi_speaker. Voice: emotion, multilingual_native. Anything else → `meta`. Extending the vocab = edit schema.py, AI parser prompt, regenerate schema.
- **Audio fields** (models): `sample_rates_hz`, `audio_formats` (lowercase) — TTS=output, STT=input; `max_text_chars` (TTS), `max_audio_seconds` (STT). Unknown = empty/null. Never guess numbers.
- **pricing**: `{unit, price_usd, free_quota?, variants?, as_of, source_url, notes?}`; unit ∈ character|minute|second|word|token|request|hour. Omit unless an explicit number is published.
- **Lineage** (models): `released_on` (partial ISO date as published), `recommended` (true = vendor docs point new
  integrations to it, + `recommended_for`; false = legacy; null = no signal), `replaces` (same-provider, same-type ids).
  Vendor pages only, never inferred. The provider page "Start here" header (views.start_here) shows only
  `recommended=true` models — no recommendation, no header. API providers get them via `scripts/apply_docs.py`.
- **v2 model fields**: `family` (root id), `alias_of` (for `-latest` aliases), `snapshot_date`, `interfaces` (http|websocket|grpc|webrtc), `batch`, `open_weights {license,url}`, `provenance {method: api|docs|manual, urls, as_of}`. Syncers can pass `family`/`snapshot_date`/`alias_of`/`batch` via `meta` keys (`parent_model_id`, `snapshot_date`, `alias_of`, `batch`, `released_on`, `recommended`, `recommended_for`, `replaces`) — merge promotes them to fields.
- **Model types**: `stt`, `tts`, `sts` (speech-to-speech/realtime; `SyncResult.sts_models`). Provider `type` is derived from active models on every sync.
- **Retired providers** (shut down, or no longer sold to new customers): set `retired=True` on the registry entry
  (sync skips it) and hand-write `data/<id>/provider.json` with `status: "deprecated"`, `retired_on` (if a date is
  published) and the reason + evidence in `description`. Never delete them — "is X still alive?" is a question the
  catalog answers. Currently: humeai (2026-11-13), lmnt, lovoai, resemble.
- **provider.json editorial fields** (`website`, `description`, `access` [self_serve|enterprise|regional|open_weights],
  `headquarters` [ISO 3166-1 alpha-2], `regions`, `compliance` [soc2|hipaa|gdpr|iso27001|pci_dss], `links`) are
  hand-curated; sync never overwrites them. Research passes write `.sync-cache/<id>_editorial.json`, applied with
  `scripts/apply_editorial.py <id> --write`.
- **verified** (provider.json, editorial): `{on, by, scope, evidence}` set only when someone at the provider confirms
  the listing (`by` = a role, never a person's name). Pages show "Verified by X on date" and count records changed
  since. Not an endorsement: never affects sorting. Policy: `docs/verification.md`.
- **Open weights**: publishers without a hosted API are synced from the Hugging Face Hub API
  (`voicedex/sync/huggingface.py`, one class per org in `open_weights.py`; popularity bar, no hard-coded repos).
  `open_weights.commercial_use` is derived from the licence (null when unclear). A retired API seller that still
  publishes weights keeps `retired=True` and sets `open_weights_path` on its registry entry.
- **Which providers belong** (inclusion policy, waves, watchlist): `docs/design/provider-expansion.md`.
  Docs extraction rules for agents: `docs/design/extraction-spec.md`.

## Adding a provider

1. `voicedex/sync/{id}.py`: subclass `ProviderSyncer`, set `provider_id`, `source` (`api|docs|mixed`), implement `sync()` → `SyncResult` (empty lists for unsupported types; set `api_urls`/`docs_urls`).
2. Use provider APIs where they exist; otherwise `parse_models_from_docs` / `parse_voices_from_docs` (cache-backed). **Never hardcode models/voices/languages**, and don't enumerate model ids inside AI guidance strings either — new upstream models must flow in automatically.
3. Register once in `voicedex/sync/registry.py`; add any key to `config.py` + `.env.example`.
4. Sync with `--write`, fill editorial fields in `data/{id}/provider.json`, run `scripts/validate.py`, add a parsing test with a recorded payload (see `tests/test_deepgram.py`).

## Local dev

```bash
uv sync --extra dev --extra sync
uv run uvicorn voicedex.main:app --reload --reload-include "data/**/*.json" --port 8001   # 8000 is taken locally
uv run pytest
uvx ruff check .
```

## Public API

| Path | Notes |
|---|---|
| `GET /v1/providers`, `/v1/providers/{id}` | provider list/detail with model & voice counts |
| `GET /v1/providers/{id}/models`, `/models/{model_id}` | filters: type, language, capabilities (ALL), lifecycle, region, search |
| `GET /v1/providers/{id}/voices`, `/voices/{voice_id}` | filters: gender, category, language, model, accent, capabilities, search |
| `GET /v1/models`, `/v1/voices` | same filters across providers, plus `provider` |
| `GET /v1/catalog.json` | entire catalog incl. deprecated, one response |
| `GET /health` | |
| `POST /mcp` | MCP (Streamable HTTP): search_models, get_model, compare_models, estimate_cost, find_alternatives, search_voices, list_providers, recent_changes |

All list endpoints: `limit`/`offset`, `updated_since` (date granularity; auto-includes deprecated unless
`include_deprecated=false`). Every `/v1` response carries one catalog-wide `ETag` (304 on `If-None-Match`) and
`Cache-Control: public, max-age=300`. Public `id`s are UUIDv5 of natural keys — stable across deploys.
