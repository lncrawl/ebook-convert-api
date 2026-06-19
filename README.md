# ebook-convert-api

A minimal Docker HTTP API that wraps [Calibre's `ebook-convert`](https://manual.calibre-ebook.com/generated/en/ebook-convert.html) pipeline. Upload a file, get the converted ebook back. Uses the official Calibre Linux binary — no source build required.

## Quick start

```sh
docker run -p 8000:8000 --cpus=2 --memory=2g ghcr.io/lncrawl/ebook-convert-api:latest
```

Convert an EPUB to MOBI:

```sh
curl -s \
  -F "file=@book.epub" \
  -F "output_format=mobi" \
  http://localhost:8000/convert \
  --output book.mobi
```

With conversion options:

```sh
curl -s \
  -F "file=@book.epub" \
  -F "output_format=epub" \
  -F 'options={"base_font_size": 12, "margin_top": 36, "embed_all_fonts": true}' \
  http://localhost:8000/convert \
  --output book-restyled.epub
```

## API

### `POST /convert`

Converts a file. Blocks until done, then streams the result and cleans up.

**Request** — `multipart/form-data`:

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `file` | upload | yes | Input ebook. Format detected from filename extension. |
| `output_format` | string | yes | Target format: `epub`, `mobi`, `azw3`, `pdf`, … |
| `options` | JSON string | no | Serialized [ConversionOptions](#conversion-options) |

**Response** — binary file with `Content-Disposition: attachment`.

| Status | Meaning |
| --- | --- |
| `200` | Converted file |
| `400` | Conversion failed — body contains Calibre error detail |
| `413` | Upload exceeds `MAX_UPLOAD_MB` |
| `422` | Invalid `options` JSON |
| `503` | All workers busy — retry after a moment |
| `504` | Conversion timed out |

### `GET /formats`

Returns the full list of supported input and output formats.

```json
{
  "input_formats": ["azw", "epub", "fb2", "mobi", "pdf", ...],
  "output_formats": ["azw3", "epub", "mobi", "pdf", ...]
}
```

### `GET /formats/{in_fmt}/{out_fmt}/options`

Returns Calibre option metadata for a specific format pair (pre-generated at image build time) — useful for building UIs or validating `extra_options` keys.

### `GET /health`

```json
{
  "status": "ok",
  "calibre_version": "9.9.0",
  "max_concurrent_jobs": 2
}
```

### `GET /ready`

Lightweight readiness probe used by Docker and Kubernetes health checks.

---

## Conversion options

`options` is a JSON object matching `ConversionOptions`. All fields are optional.

### Universal fields

| Field | Type | Description |
| --- | --- | --- |
| `base_font_size` | float | Base font size in pts |
| `margin_top/bottom/left/right` | float | Page margins in pts |
| `extra_css` | string | Extra CSS applied after all other CSS |
| `embed_all_fonts` | bool | Embed every referenced font |
| `smarten_punctuation` | bool | Convert plain quotes/dashes to typographic |
| `enable_heuristics` | bool | Enable heuristic processing |
| `title`, `authors`, `publisher` | string | Metadata overrides |
| `language` | string | Language code (e.g. `en`, `fr`) |
| `input_profile` | string | Input device profile (e.g. `default`, `kindle`) |
| `output_profile` | string | Output device profile (e.g. `default`, `kobo`, `kindle`) |
| `verbose` | int (0–2) | Calibre log verbosity |

Full field reference: [`app/models/options_universal.py`](app/models/options_universal.py)

### Format-specific flags via `extra_options`

Pass any Calibre CLI flag not in the universal list through `extra_options`. Keys can use hyphens or underscores, with or without `--`. Boolean flags use `null`.

```json
{
  "extra_options": {
    "epub-version": "3",
    "no-default-epub-cover": null,
    "mobi-file-type": "both"
  }
}
```

> **Security:** Filesystem-path flags (`--debug-pipeline`, `--extract-to`, `--cover`, `--transform-css-rules`) are blocked by the server regardless of what is sent.

---

## Configuration

Environment variables (all optional):

| Variable | Default | Description |
| --- | --- | --- |
| `MAX_CONCURRENT_JOBS` | auto | Worker count. `0` re-derives from cgroup limits. |
| `MEMORY_PER_JOB_MB` | `256` | Per-job memory budget used for auto-sizing. |
| `CONVERSION_TIMEOUT_SECONDS` | `300` | Per-job timeout. `504` returned on breach. |
| `MAX_UPLOAD_MB` | `100` | Upload size limit. `413` returned on breach. |
| `USE_AUTH` | `false` | Enable auth middleware stub (not yet implemented). |

### Concurrency auto-sizing

When `MAX_CONCURRENT_JOBS=0` (the default), the server reads Docker cgroup v2 limits at startup:

```py
max_workers = min(cpu_quota, memory_limit_mb / MEMORY_PER_JOB_MB)
```

So `docker run --cpus=2 --memory=1g` → 2 workers from CPU but only `1024 / 256 = 4` from memory → `min(2, 4) = 2` workers.

---

## Building

Install [`uv`](https://docs.astral.sh/uv/) and [`poethepoet`](https://github.com/nat-n/poethepoet), then:

```sh
uv sync
```

The `poe` task runner wraps all common workflows:

```sh
poe build        # docker build -t ebook-convert-api .
poe up           # run production container on :8000
poe dev          # run dev container with live-reload (bind-mounts ./app)
poe lint         # ruff check
poe fmt          # ruff format
poe typecheck    # pyright
```

To upgrade Calibre: change `CALIBRE_VERSION` in the Dockerfile, then `poe build`.

> **Note:** Format option stubs (`data/format_stubs/`) are generated automatically during `docker build` by running `calibre-debug` against every supported format pair. They are gitignored — do not commit them.

---

## Development

The app always runs inside Docker. `poe dev` bind-mounts `./app` into the container and starts uvicorn with `--reload`, so local edits trigger an automatic server restart without rebuilding the image.

```sh
poe dev
# edit any file under app/ → server reloads automatically
```

Add a dependency:

```sh
uv add <package>
```

Regenerate the lockfile after manual `pyproject.toml` edits:

```sh
uv lock
```

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
