# ebook-convert-api

[![Lint](https://github.com/lncrawl/ebook-convert-api/actions/workflows/lint.yml/badge.svg)](https://github.com/lncrawl/ebook-convert-api/actions/workflows/lint.yml)
[![Docker build](https://github.com/lncrawl/ebook-convert-api/actions/workflows/docker-build.yml/badge.svg)](https://github.com/lncrawl/ebook-convert-api/actions/workflows/docker-build.yml)
[![Dependabot Updates](https://github.com/lncrawl/ebook-convert-api/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/lncrawl/ebook-convert-api/actions/workflows/dependabot/dependabot-updates)

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

| Field           | Type        | Required | Description                                                                   |
| --------------- | ----------- | -------- | ----------------------------------------------------------------------------- |
| `file`          | upload      | yes      | Input ebook. Format detected from filename extension.                         |
| `output_format` | string      | yes      | Target format: `epub`, `mobi`, `azw3`, `pdf`, …                               |
| `options`       | JSON string | no       | Flat `{option: value}` object — see [Conversion options](#conversion-options) |

**Response** — binary file with `Content-Disposition: attachment`.

| Status | Meaning                                                |
| ------ | ------------------------------------------------------ |
| `200`  | Converted file                                         |
| `400`  | Conversion failed — body contains Calibre error detail |
| `413`  | Upload exceeds `MAX_UPLOAD_MB`                         |
| `422`  | Invalid `options` JSON                                 |
| `503`  | All workers busy — retry after a moment                |
| `504`  | Conversion timed out                                   |

### `GET /formats`

Returns the full list of supported input and output formats.

```json
{
  "input_formats": ["azw", "epub", "fb2", "mobi", "pdf", ...],
  "output_formats": ["azw3", "epub", "mobi", "pdf", ...]
}
```

### `GET /formats/{in_fmt}/{out_fmt}/options`

Returns every Calibre option valid for that conversion, grouped by category (pre-generated at image build time) — useful for building UIs or discovering option names. Each group has a `group` label and a list of option metadata (`name`, `cli_flag`, `help`, `type`, `default`, `choices`). The groups are: `Input` (input-format options), the shared categories (`Look & Feel`, `Structure Detection`, `Table of Contents`, `Heuristic Processing`, `Search & Replace`, `Metadata`, `General`, `Debug`), and `Output` (output-format options).

```json
[
  {
    "group": "Look & Feel",
    "options": [
      {
        "name": "base_font_size",
        "cli_flag": "--base-font-size",
        "help": "The base font size in pts...",
        "type": "float",
        "default": 0,
        "choices": null
      }
    ]
  }
]
```

Responds `404` if either format is not supported.

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

`options` is a flat JSON object of `{option_name: value}` pairs — all optional. The keys are Calibre option names as returned by [`GET /formats/{in}/{out}/options`](#get-formatsin_fmtout_fmtoptions); keys may use hyphens or underscores, with or without a leading `--`. A `null` value means a boolean flag (passed with no argument). Keys you omit fall back to Calibre's own defaults.

```json
{
  "base_font_size": 12,
  "margin_top": 36,
  "embed_all_fonts": true,
  "epub-version": "3",
  "no-default-epub-cover": null
}
```

Call the options endpoint for a given format pair to discover the full set of valid keys, their types, defaults, and allowed `choices`.

> **Security:** Filesystem-path flags (`--debug-pipeline`, `--extract-to`, `--cover`, `--transform-css-rules`) are blocked by the server regardless of what is sent.

---

## Configuration

Environment variables (all optional):

| Variable                     | Default | Description                                        |
| ---------------------------- | ------- | -------------------------------------------------- |
| `MAX_CONCURRENT_JOBS`        | auto    | Worker count. `0` re-derives from cgroup limits.   |
| `MEMORY_PER_JOB_MB`          | `256`   | Per-job memory budget used for auto-sizing.        |
| `CONVERSION_TIMEOUT_SECONDS` | `300`   | Per-job timeout. `504` returned on breach.         |
| `MAX_UPLOAD_MB`              | `100`   | Upload size limit. `413` returned on breach.       |
| `USE_AUTH`                   | `false` | Enable auth middleware stub (not yet implemented). |

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

> **Note:** The option catalog (`data/catalog.json`) is generated by running `calibre-debug` against the installed Calibre — automatically during `docker build`, or locally with `poe generate-catalog`. The committed copy is what the API serves.

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
