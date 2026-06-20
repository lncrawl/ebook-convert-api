# ebook-convert-api

[![codecov](https://codecov.io/gh/lncrawl/ebook-convert-api/graph/badge.svg?token=GE91YGCUUU)](https://codecov.io/gh/lncrawl/ebook-convert-api)
[![Lint](https://github.com/lncrawl/ebook-convert-api/actions/workflows/lint.yml/badge.svg)](https://github.com/lncrawl/ebook-convert-api/actions/workflows/lint.yml)
[![Docker build](https://github.com/lncrawl/ebook-convert-api/actions/workflows/docker-build.yml/badge.svg)](https://github.com/lncrawl/ebook-convert-api/actions/workflows/docker-build.yml)
[![Dependabot Updates](https://github.com/lncrawl/ebook-convert-api/actions/workflows/dependabot/dependabot-updates/badge.svg)](https://github.com/lncrawl/ebook-convert-api/actions/workflows/dependabot/dependabot-updates)

A minimal Docker HTTP API that wraps [Calibre's `ebook-convert`](https://manual.calibre-ebook.com/generated/en/ebook-convert.html) pipeline. Upload a file, get the converted ebook back. Uses the official Calibre Linux binary — no source build required.

## Quick start

```sh
docker run -p 8000:8000 --cpus=2 --memory=3g ghcr.io/lncrawl/ebook-convert-api:latest
```

Convert an EPUB to MOBI:

```sh
curl -s \
  -F "file=@book.epub" \
  -F "output_format=mobi" \
  http://localhost:8000/convert \
  --output book.mobi
```

With conversion options (each option is its own form field):

```sh
curl -s \
  -F "file=@book.epub" \
  -F "output_format=epub" \
  -F "base_font_size=12" \
  -F "margin_top=36" \
  -F "embed_all_fonts=true" \
  http://localhost:8000/convert \
  --output book-restyled.epub
```

## API

### `POST /convert`

Converts a file. Blocks until done, then streams the result and cleans up.

**Request** — `multipart/form-data`:

| Field           | Type   | Required | Description                                                                         |
| --------------- | ------ | -------- | ----------------------------------------------------------------------------------- |
| `file`          | upload | yes      | Input ebook. Format detected from filename extension.                               |
| `output_format` | enum   | yes      | Target format: `epub`, `mobi`, `azw3`, `pdf`, ...                                   |
| _option fields_ | varies | no       | One typed field per Calibre option — see [Conversion options](#conversion-options). |

**Response** — binary file with `Content-Disposition: attachment`.

| Status | Meaning                                                  |
| ------ | -------------------------------------------------------- |
| `200`  | Converted file                                           |
| `400`  | Conversion failed — body contains Calibre error detail   |
| `413`  | Upload exceeds `MAX_UPLOAD_MB`                           |
| `422`  | Invalid `output_format` or an option with the wrong type |
| `503`  | All workers busy — retry after a moment                  |
| `504`  | Conversion timed out                                     |

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

Every Calibre conversion option is exposed as its own **typed** form field on `POST /convert`,
so the interactive docs at `/docs` render number/boolean inputs, enum dropdowns, and per-option
help. All option fields are optional — omit a field and Calibre's own default applies.

```sh
curl -s \
  -F "file=@book.epub" \
  -F "output_format=epub" \
  -F "base_font_size=12" \
  -F "embed_all_fonts=true" \
  -F "epub_version=3" \
  http://localhost:8000/convert \
  --output book.epub
```

The form advertises the **union** of options across all formats. Only the options valid for the
chosen `input → output` pair are applied; any others you send are ignored. To discover the exact
set, types, defaults, and allowed `choices` for a given pair, call
[`GET /formats/{in}/{out}/options`](#get-formatsin_fmtout_fmtoptions).

> **Security:** Filesystem-path flags (`--debug-pipeline`, `--extract-to`, `--cover`, `--transform-css-rules`) are not exposed and are blocked by the server regardless of what is sent.

---

## Configuration

Environment variables (all optional):

| Variable                     | Default | Description                                        |
| ---------------------------- | ------- | -------------------------------------------------- |
| `MAX_CONCURRENT_JOBS`        | `2`     | Worker count (`ProcessPoolExecutor` size).         |
| `CONVERSION_TIMEOUT_SECONDS` | `300`   | Per-job timeout. `504` returned on breach.         |
| `MAX_UPLOAD_MB`              | `100`   | Upload size limit. `413` returned on breach.       |
| `USE_AUTH`                   | `false` | Enable auth middleware stub (not yet implemented). |

### Concurrency

`MAX_CONCURRENT_JOBS` sets the number of worker processes directly. Size it to the
container's CPU allocation and the memory each `ebook-convert` job needs (the PDF path,
via headless QtWebEngine, is the heaviest at ~350–550 MB per job). For example
`docker run --cpus=4 --memory=3g` comfortably runs `MAX_CONCURRENT_JOBS=4`.

---

## Building

Install [`uv`](https://docs.astral.sh/uv/) and [`poethepoet`](https://github.com/nat-n/poethepoet), then:

```sh
uv sync
```

The `poe` task runner wraps all common workflows:

```sh
# Run production container (builds the image; the option catalog is generated during that build)
poe up

# Run dev container (live-reloads on local file changes via bind-mount)
poe dev
poe dev-exec          # open a shell in the running dev container

# Lint / format / typecheck
poe check

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
