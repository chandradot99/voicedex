# v2 architecture — data in git, API in memory

Status: accepted (2026-11-16). Owner: Claude Code (delegated product owner).

## Goals

1. **Trustworthy** — every change to the catalog is a reviewable, revertible git diff with provenance.
2. **Cheap to keep fresh** — re-syncing a provider is one command; nothing is ever extracted twice for
   the same upstream state; a bad fetch can't silently wipe data.
3. **Easy to adopt** — a stable JSON contract (JSON Schema), one static `catalog.json`, the filterable
   REST API, and later npm/PyPI packages.
4. **Zero-ops** — no database to run, migrate, back up or promote.

## Decisions

### D1. The catalog lives in `data/` as JSON files. Git is the database.

```
data/<provider_id>/provider.json   # provider record (partly hand-curated)
data/<provider_id>/models.json     # all models, sorted by (type, id)
data/<provider_id>/voices.json     # all voices, sorted by id
```

- **JSON, not YAML** — YAML 1.1 parses the Norwegian language code `no` as `false`, and our data is full
  of language codes. JSON is unambiguous and every language reads it natively.
- Deterministic output (sorted keys, 2-space indent, trailing newline) so diffs show only real changes.
- Per-provider files, not per-record: syncers regenerate a whole provider at once, and providers like
  Google/Azure have 1–2k voices — one file per voice would be noise.
- History, rollback and audit come from git. Price history = `git log -p data/*/models.json`.

### D2. The API loads `data/` into memory at startup. No Postgres.

The whole catalog is a few MB. Filtering in Python is sub-millisecond and removes the DB, migrations,
the dev→prod promote step (and its bugs), Neon cold starts and the `updated_at` drift between envs.
Deploying a commit *is* publishing that version of the data. If a future Pro feature needs a DB
(alerts, accounts), it gets one then — the public catalog stays file-backed.

### D3. The schema is defined once, in Pydantic, and exported as JSON Schema.

`voicedex/catalog/schema.py` is the contract. `schema/*.schema.json` is generated from it and checked in
for non-Python consumers. Controlled vocabularies (capabilities, regions, lifecycle, interfaces,
compliance) are enums — invalid values fail validation on **write** and in CI, not just at query time.

### D4. Sync = fetch → validate → merge → guard → write → diff.

`scripts/sync.py <provider>` runs the syncer (unchanged contract: returns `SyncResult`), then:

- **merge** with the existing files: new records get `first_seen`; changed records get `updated_at`;
  records missing upstream are kept and marked `deprecated` (never deleted); records that reappear are
  revived.
- **guard** — refuses to write if incoming is empty while data exists, or if more than 25% of active
  models or voices would be deprecated in one run. Override with `--allow-shrink` after checking.
- **diff** — prints a per-record, per-field change report (the old "~N updated" count is gone).
- Dry-run by default; `--write` writes files. Then commit / open a PR — the PR is the review step.

### D5. Provenance on every model; voices carry provider-level provenance.

`model.provenance = {method: api|docs|manual, urls: [...], as_of: date}`. Voices are almost always
from one API listing, so their source lives in `provider.json` (`voices_source`). Consumers can tell
AI-extracted data from API data.

### D6. Stable public IDs.

API `id` fields are UUIDv5 of the natural key (`provider/type/model_id`, `provider/voice_id`) —
identical in every environment and across rebuilds. Response shapes for `/v1` stay compatible.

### D7. Hand-curated fields are never overwritten by sync.

`provider.json` holds editorial fields (description, website, compliance, regions, links) that sync
leaves alone; sync owns only derived fields (`type`, `last_synced`, sources). Same rule for any field a
syncer leaves `None`/empty: the existing value is kept rather than erased (prevents a docs page that
forgot to mention pricing from wiping known pricing).

## Schema v2 additions (over v1)

| Record | New fields |
|---|---|
| Provider | `status`, `regions`, `compliance` (soc2, hipaa, gdpr, iso27001, pci_dss), `links` {docs, api_reference, pricing, status}, `voices_source`, `last_synced` |
| Model | `family`, `alias_of`, `snapshot_date`, `interfaces` (http, websocket, grpc, webrtc), `batch`, `open_weights` {license, url}, `provenance`, `first_seen`, `updated_at`, `deprecated_at` (date) |
| Voice | `first_seen`, `updated_at`, `deprecated_at` (date) |
| Model type | adds `sts` (speech-to-speech / realtime) alongside `stt`, `tts` |

Deferred (tracked, not built yet): per-locale voice accents, latency/quality benchmarks, pricing
history API, changelog/RSS feed, npm/PyPI packages, Pro tier.

## Removed

Postgres, SQLAlchemy models, Alembic, `scripts/promote.py`, dev DB, `sync_runs` (git log replaces it).

## D8. Web catalog UI: server-rendered from the same in-memory catalog (2026-11-16)

The homepage and catalog pages (`/`, `/providers/{id}`, `/models`, `/voices`, `/search`) are Jinja2
templates rendered by the API process (`voicedex/web/`), not a separate SPA.

- **Why:** `/v1/catalog.json` is ~8 MB, too heavy to ship to browsers for client-side filtering; server
  rendering keeps pages fast, indexable by search engines (per-provider pages are the long-tail entry
  point), and deployed atomically with the data they show — no second build or host.
- Filters are plain GET forms (shareable URLs) using the API's matching semantics.
- No JS framework; one small script for voice-sample playback.
- Site name is `SITE_NAME` (config) until the product is named.
