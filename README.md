# Voice Provider Registry

An open catalog of voice AI providers: speech-to-text, text-to-speech and speech-to-speech models,
voices, languages, capabilities, pricing and regions. It is normalized across providers and you can
query it as a REST API or download it as one JSON file. (A new project name and homepage are coming.)

- **Data you can audit.** The whole catalog lives in [`data/`](data/) as plain JSON in git. Every
  change is a reviewable diff, and every model records where its data came from and when.
- **One schema for every provider.** Languages are BCP-47, capabilities and regions use a controlled
  vocabulary, and voices are linked to the models they work with.
  See [`schema/`](schema/) for the JSON Schema.
- **No lock-in.** Use the API, the single [`/v1/catalog.json`](#api) export, or read `data/` directly.

## API

| Path | |
|---|---|
| `GET /v1/providers` · `/v1/providers/{id}` | Providers, with model and voice counts |
| `GET /v1/providers/{id}/models` · `/models/{model_id}` | Filters: `type`, `language`, `capabilities`, `lifecycle`, `region`, `search` |
| `GET /v1/providers/{id}/voices` · `/voices/{voice_id}` | Filters: `gender`, `category`, `language`, `model`, `accent`, `capabilities`, `search` |
| `GET /v1/models` · `/v1/voices` | The same filters across all providers, plus `provider` |
| `GET /v1/catalog.json` | Everything in one response |

Responses carry an `ETag` header, so you can poll cheaply with `If-None-Match`. List endpoints also
support `updated_since`. Interactive docs are at `/docs`.

```bash
curl "$API/v1/voices?language=en-GB&gender=female&limit=5"
curl "$API/v1/models?type=stt&capabilities=speaker_diarization&region=eu"
```

## How the data is kept fresh

Each provider has a syncer in [`naaviq/sync/`](naaviq/sync/). It calls the provider's API where one
exists, and otherwise extracts the data from the provider's documentation. `scripts/sync.py` then
merges the result into `data/`:

- New records are added.
- Records that disappeared upstream are marked deprecated, never deleted.
- A guard refuses to write if a fetch looks partial.

The diff is reviewed as a pull request, and merging publishes it.

```bash
uv sync --extra dev --extra sync
uv run python scripts/sync.py deepgram            # dry-run, prints a per-field diff
uv run python scripts/sync.py deepgram --write    # updates data/deepgram/
uv run python scripts/validate.py                 # schema and consistency checks (CI runs this too)
```

## Run locally

```bash
uv sync --extra dev
uv run uvicorn naaviq.main:app --reload
uv run pytest
```

## Contributing

To add a provider or fix data, see [`CLAUDE.md`](CLAUDE.md#adding-a-provider) for the checklist and
[`docs/design/v2-architecture.md`](docs/design/v2-architecture.md) for the design.

License: Apache 2.0
