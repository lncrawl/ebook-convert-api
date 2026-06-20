# ebook-convert-api

HTTP API wrapping Calibre's `ebook-convert` pipeline. Accepts a file upload, returns the converted ebook.

## Stack

- Python 3.14, FastAPI, uv
- Calibre official binary (self-contained) installed to `/opt/calibre/` inside Docker
- Concurrency: `ProcessPoolExecutor` sized by `MAX_CONCURRENT_JOBS`

## Commands

```sh
# Build image (generates the option catalog at build time)
poe build

# Run production container
poe up

# Run dev container (live-reloads on local file changes via bind-mount)
poe dev

# Lint / format / typecheck
poe lint
poe fmt
poe typecheck

# Dependency management
uv add <pkg>          # add a dependency
uv lock --upgrade     # upgrade all deps, regenerate uv.lock
```

## Key files

| File | Purpose |
| ---- | ------- |
| `Dockerfile` | Multi-stage build: install + prune official Calibre binary, build venv with uv, assemble a slim runtime (no uv/build tools, Mesa software-GL stripped); generates the option catalog at build time |
| `scripts/calibre_introspect.py` | Run by `calibre-debug -e` during build; introspects all formats + common pipeline options and writes `data/output.json` |
| `data/output.json` | Generated option catalog: `input_plugins`/`output_plugins` (per-format options) + `common_options` (shared options grouped by category) |
| `app/config.py` | Settings incl. `max_concurrent_jobs` |
| `app/state.py` | Shared `ProcessPoolExecutor` + `asyncio.Semaphore` |
| `app/core/converter.py` | Calls `ebook-convert` CLI via subprocess (runs in executor worker) |
| `app/core/introspector.py` | Loads `data/output.json`; derives format lists + per-pair grouped options |
| `app/core/options_builder.py` | Maps a flat `{name: value}` options dict → Plumber `SimpleNamespace` |
| `app/core/options_schema.py` | Builds the `POST /convert` signature from the catalog — one typed form field per option (enum dropdowns for `choice`), so Swagger renders rich docs |
| `app/api/convert.py` | `POST /convert` endpoint; exposes every catalog option as a typed multipart form field |

## Calibre version

Pinned via `ARG CALIBRE_VERSION` in `Dockerfile`. To upgrade: change the arg, rebuild.

## Environment variables

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `MAX_CONCURRENT_JOBS` | 2 | Worker process count (`ProcessPoolExecutor` size) |
| `CONVERSION_TIMEOUT_SECONDS` | 300 | Per-job timeout |
| `MAX_UPLOAD_MB` | 100 | Multipart upload limit |
| `USE_AUTH` | false | Set to `true` to enable `AuthMiddleware` stub |
