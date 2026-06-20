# ebook-convert-api

HTTP API wrapping Calibre's `ebook-convert` pipeline. Accepts a file upload, returns the converted ebook.

## Stack

- Python 3.14, FastAPI, uv
- Calibre official binary (self-contained) installed to `/opt/calibre/` inside Docker
- Concurrency: `ProcessPoolExecutor` sized by `MAX_CONCURRENT_JOBS`

## Conventions

- **Imports within the `app` package are relative** (e.g. `from ..core import introspector`,
  `from .config import settings`), never absolute `from app...`. Standalone scripts outside the
  package (e.g. `scripts/calibre_introspect.py`, run by `calibre-debug`) keep absolute imports.

## Commands

```sh
# Run production container (builds the image; the option catalog is generated during that build)
poe up

# Run dev container (live-reloads on local file changes via bind-mount)
poe dev
poe dev-exec          # open a shell in the running dev container

# Lint / format / typecheck
poe lint
poe format
poe typecheck

# Tests (integration tests hit a live server at API_BASE_URL, default http://localhost:8000;
# the whole session is skipped if it's unreachable — so run `poe dev`/`poe up` first)
poe test

# Regenerate the option catalog (data/catalog.json)
poe catalog           # uses local Calibre
poe catalog-dev       # uses the dev image's pinned Calibre (run while/after `poe dev`)

# Dependency management
uv add <pkg>          # add a dependency
uv lock --upgrade     # upgrade all deps, regenerate uv.lock
```

## Key files

| File | Purpose |
| ---- | ------- |
| `Dockerfile` | Multi-stage build: install + prune official Calibre binary, build venv with uv, assemble a slim runtime (no uv/build tools, Mesa software-GL stripped); generates the option catalog at build time |
| `scripts/calibre_introspect.py` | Run by `calibre-debug -e` during build; introspects all formats + common pipeline options and writes `data/catalog.json` |
| `data/catalog.json` | Generated option catalog: `input_plugins`/`output_plugins` (per-format options) + `common_options` (shared options grouped by category) |
| `app/config.py` | Settings incl. `max_concurrent_jobs` |
| `app/state.py` | Shared `ProcessPoolExecutor` + `asyncio.Semaphore`; `reset_executor()` rebuilds the pool after a worker crash |
| `app/core/converter.py` | Calls `ebook-convert` CLI via subprocess (runs in executor worker) |
| `app/core/introspector.py` | Loads `data/catalog.json`; derives format lists + per-pair grouped options |
| `app/core/options_builder.py` | Maps a validated `{name: value}` options dict → `ebook-convert` CLI args (each option's `cli_flag` + default; booleans emitted only when they differ from the default) |
| `app/core/options_schema.py` | Builds the `POST /convert` signature from the catalog — one typed form field per option (enum dropdowns for `choice`), so Swagger renders rich docs |
| `app/api/convert.py` | `POST /convert` endpoint; exposes every catalog option as a typed multipart form field |
| `app/api/ui.py` | Serves `GET /` — a Jinja-rendered single-page UI with `app/static/{styles.css,app.js}` inlined and the format lists injected (no client `fetch("/formats")`) |

## Environment variables

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `MAX_CONCURRENT_JOBS` | 2 | Worker process count (`ProcessPoolExecutor` size) |
| `CONVERSION_TIMEOUT_SECONDS` | 300 | Per-job timeout |
| `MAX_UPLOAD_MB` | 100 | Multipart upload limit |
| `USE_AUTH` | false | Set to `true` to enable `AuthMiddleware` stub |
