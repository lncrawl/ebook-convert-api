# ebook-convert-api

HTTP API wrapping Calibre's `ebook-convert` pipeline. Accepts a file upload, returns the converted ebook.

## Stack

- Python 3.14, FastAPI, uv
- Calibre built from source (Qt stripped) inside Docker
- Concurrency: `ProcessPoolExecutor` sized from Docker cgroup CPU/memory limits

## Commands

```sh
# Build image (pin Calibre version via build arg)
docker build --build-arg CALIBRE_VERSION=9.9.0 -t ebook-convert-api .

# Run (resource limits drive concurrency auto-sizing)
docker run -p 8000:8000 --cpus=2 --memory=2g ebook-convert-api

# Local dev (requires Calibre installed with PYTHONPATH=/usr/local/lib)
uv run uvicorn app.main:app --reload

# Dependency management
uv add <pkg>          # add a dependency
uv lock --upgrade     # upgrade all deps, regenerate uv.lock
```

## Key files

| File | Purpose |
| ---- | ------- |
| `docker/patch_calibre.py` | Removes Qt deps from Calibre source before build |
| `Dockerfile` | Two-stage build: compile Calibre → slim runtime |
| `app/config.py` | Settings + cgroup-aware `max_concurrent_jobs` |
| `app/state.py` | Shared `ProcessPoolExecutor` + `asyncio.Semaphore` |
| `app/core/converter.py` | Calibre `Plumber` wrapper (runs in executor worker) |
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
