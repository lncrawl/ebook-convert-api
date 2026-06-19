# ebook-convert-api

HTTP API wrapping Calibre's `ebook-convert` pipeline. Accepts a file upload, returns the converted ebook.

## Stack

- Python 3.14, FastAPI, uv
- Calibre official binary (self-contained) installed to `/opt/calibre/` inside Docker
- Concurrency: `ProcessPoolExecutor` sized from Docker cgroup CPU/memory limits

## Commands

```sh
# Build image (generates format stubs at build time)
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
| `Dockerfile` | Two-stage build: install official Calibre binary → slim runtime; generates format stubs at build time |
| `scripts/calibre_introspect.py` | Run by `calibre-debug -e` during build; introspects one format pair and prints JSON |
| `scripts/generate_stubs.py` | Build-time script; iterates all format pairs and writes stubs to `data/format_stubs/` |
| `app/config.py` | Settings + cgroup-aware `max_concurrent_jobs` |
| `app/state.py` | Shared `ProcessPoolExecutor` + `asyncio.Semaphore` |
| `app/core/converter.py` | Calls `ebook-convert` CLI via subprocess (runs in executor worker) |
| `app/core/introspector.py` | Loads pre-generated format option stubs from `data/format_stubs/` |
| `app/core/options_builder.py` | Maps `ConversionOptions` → Plumber `SimpleNamespace` |
| `app/api/convert.py` | `POST /convert` endpoint |

## Calibre version

Pinned via `ARG CALIBRE_VERSION` in `Dockerfile`. To upgrade: change the arg, rebuild.

## Environment variables

| Variable | Default | Notes |
| -------- | ------- | ----- |
| `MAX_CONCURRENT_JOBS` | auto | Set to 0 to re-derive from cgroups |
| `MEMORY_PER_JOB_MB` | 256 | Used for memory-based concurrency limit |
| `CONVERSION_TIMEOUT_SECONDS` | 300 | Per-job timeout |
| `MAX_UPLOAD_MB` | 100 | Multipart upload limit |
| `USE_AUTH` | false | Set to `true` to enable `AuthMiddleware` stub |
