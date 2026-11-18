---
name: catalog-refresh
description: Voicedex catalog maintenance run inside Claude Code (no Anthropic API key). Checks data freshness, shutdown dates, dead voice samples and stale prices, re-syncs what is due, and (in discover mode) researches new voice-AI providers to add. Use when the user runs /catalog-refresh or asks to refresh, update, audit or check the catalog for new providers.
argument-hint: "[freshness | discover | all | <provider-id> ...]  (default: freshness)"
---

# /catalog-refresh — keep Voicedex current

You are the maintainer. Work on a branch, one commit per provider, and stop before anything public: **never merge to
main or push without the user's explicit OK in this session** (pushing main deploys voicedex.dev). Never use
`ANTHROPIC_API_KEY`: docs extraction is done by you / your subagents writing `.sync-cache/` (CLAUDE.md).

Read first: `CLAUDE.md` (workflow, data conventions, merge rules), `docs/design/extraction-spec.md` (agent brief for
docs extraction), `docs/design/provider-expansion.md` §1 (inclusion policy + edge-case rules) and §5 (watchlist).

## Modes (from the argument)

- `freshness` (default): steps 1–5.
- `discover`: steps 1, 6, 5.
- `all`: steps 1–6.
- one or more provider ids: re-sync just those (steps 3–5).

## 1. Health report

```bash
git status --short && git switch -c refresh/$(date +%F)     # stop if the tree is dirty; ask the user
uv run python scripts/catalog_health.py --samples          # ~2 min with --samples
```

Show the user a short summary (counts per section). It lists: stale syncs (thresholds by source), registered-but-never-
synced, models past or near their `eol_date`, active providers past `retired_on`, prices older than 120 days, whether
discovery is due, dead sample links.

## 2. Plan the batch (keep a session to a sane size)

Priority order: shutdown date passed → dead samples → near-term shutdowns → stale `api`/`mixed` → stale `docs` →
stale prices. Cap a run at ~10 docs re-extractions (they need agents); API re-syncs are cheap, do them all. Tell the
user the plan in a few lines, then proceed without waiting unless something needs their decision.

## 3. Re-sync

**API / mixed providers** (voices and API-listed models refresh; reviewed docs records are reused):
```bash
uv run python scripts/sync.py <id> --reuse-docs            # dry-run: read the diff
uv run python scripts/sync.py <id> --reuse-docs --write
```
A syncer that fails for a missing/expired key: note it for the user (keys are theirs), move on. Google
`GoogleAuthExpired` → ask the user to run `! gcloud auth application-default login`.

**Docs providers / docs sections** (prices, new models, shutdown dates change on vendor pages): spawn general-purpose
subagents (3–4 providers each, in parallel) with this brief: *"Follow docs/design/extraction-spec.md for providers
<ids>. Start from the current records in data/<id>/models.json — keep what is still true, update what changed, add new
models, set eol_date only from an official page. Write .sync-cache files, dry-run `scripts/sync.py <id>` (never
--write), report changes with source URLs."* Review each report, then `sync.py <id> --write`.

Rules that matter (from experience):
- **Verify lifecycle dates on the vendor's own page** before writing them (a research summary once had a Gemini
  shutdown date wrong by a month).
- **Guard refusals** (`would deprecate >25%`) mean investigate — usually a partial fetch or a renamed endpoint. Only use
  `--allow-shrink` after confirming the shrink is real.
- Never guess numbers; prices only from the vendor's page, in its currency.
- Sync drops dead sample links on definitive 4xx itself (`meta.preview_unavailable`); nothing extra to do.
- A provider that shut down / stopped selling → retire it per CLAUDE.md "Retired providers" (never delete).

## 4. Review and land

Per provider: `git diff --stat data/<id>`, sanity-check surprising changes, then
```bash
uv run python scripts/validate.py && uv run pytest -q && uvx ruff check .
git add data/<id> [voicedex/sync/<id>.py] && git commit -m "<Provider>: <what changed>"
```
Update `docs/design/provider-expansion.md` "Status" only for notable events (new provider, retirement).

## 5. Report

End with a short summary: what changed per provider, what failed and why (missing key, guard, site down), what needs
the user (keys, decisions), and the branch name. Ask whether to merge and deploy.

## 6. Discover new providers (when due, or asked)

Goal: find speech model owners (STT/TTS/STS, API or open weights) we don't list, and lifecycle news for ones we do.
Spawn 4 research subagents in parallel (general-purpose; WebSearch/WebFetch; `curl -A "Mozilla/5.0"` when a site
blocks fetches), each given: the current provider ids (`ls data/`), the watchlist (§5), the inclusion policy (§1), and
one segment:

1. US / Canada / Europe API vendors and clouds — cross-check the Artificial Analysis TTS and STT leaderboards.
2. China, Japan, Korea, Taiwan, Southeast Asia.
3. India, MENA, Africa, Latin America, Russia/CIS, plus the open coverage holes listed in §5.
4. Open-weights orgs — query the Hugging Face API (`/api/models?pipeline_tag=text-to-speech|automatic-speech-recognition|text-to-audio&sort=trendingScore|likes|downloads`), apply the §1 bar; plus 2025–26 news: launches, funding, acquisitions, shutdowns of catalogued providers.

Each returns: QUALIFY (id, types, HQ, access, docs URL, pricing URL), WATCH (one-line reason), EXCLUDE (reason), and
lifecycle events with source URLs. Notes go to `research_notes/<date>/` (git-excluded).

Then: re-check watchlist entries mentioned, add QUALIFY providers the usual way (CLAUDE.md "Adding a provider";
docs syncer stubs via `DocsOnlySyncer`, HF orgs via `voicedex/sync/open_weights.py`, extraction by subagents per the
spec), apply lifecycle events, update §5 (watchlist, coverage holes) and set
`Last discovery pass: <today>` in `docs/design/provider-expansion.md`.
