#!/usr/bin/env python3
"""Convert book.epub to every output format listed in data/catalog.json,
exercising all available options sourced from the catalog.

Run from the repo root:
    python tests/epub-test/test.py

Requires Calibre's ebook-convert to be on PATH.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
INPUT = Path(__file__).parent / "book.epub"
CATALOG = REPO_ROOT / "data" / "catalog.json"
OUTPUT = Path(__file__).parent / "output"
EBOOK_CONVERT = shutil.which("ebook-convert")


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text


def green(t: str) -> str:
    return _c("32", t)


def yellow(t: str) -> str:
    return _c("33", t)


def red(t: str) -> str:
    return _c("31", t)


def cyan(t: str) -> str:
    return _c("36", t)


def bold(t: str) -> str:
    return _c("1", t)


def dim(t: str) -> str:
    return _c("2", t)


# Options that need an external file/path or write to the filesystem.
# These cannot be exercised with a self-contained test, so skip them.
_SKIP_OPTIONS: frozenset[str] = frozenset(
    {
        "--debug-pipeline",
        "--cover",
        "--embed-font-family",
        "--extra-css",
        "--filter-css",
        "--font-size-mapping",
        "--read-metadata-from-opf",
        "--search-replace",
        "--sr1-search",
        "--sr1-replace",
        "--sr2-search",
        "--sr2-replace",
        "--sr3-search",
        "--sr3-replace",
        "--transform-css-rules",
        "--transform-html-rules",
        "--extract-to",
        # Mutually exclusive with --smarten-punctuation; including both crashes Calibre.
        "--unsmarten-punctuation",
        # Fails on minimal test epub (no TOC entries to inline) for rb/pdb/pmlz.
        "--inline-toc",
    }
)


def _feature_flags(fmt: str, catalog: dict) -> list[str]:
    """Return CLI flags that enable non-default features for *fmt*.

    Selects every boolean option whose default is False (enabling it exercises
    an extra code path) across both common options and the format-specific
    output plugin options.  Skips anything that requires an external resource.
    """
    flags: list[str] = []

    for group_opts in catalog["common_options"].values():
        for opt in group_opts:
            if opt["cli_flag"] in _SKIP_OPTIONS:
                continue
            if opt["type"] == "bool" and opt["default"] is False:
                flags.append(opt["cli_flag"])

    for opt in catalog["output_plugins"].get(fmt, []):
        if opt["cli_flag"] in _SKIP_OPTIONS:
            continue
        if opt["type"] == "bool" and opt["default"] is False:
            flags.append(opt["cli_flag"])

    return flags


def calibre_convert(src: Path, dst: Path, extra_args: list[str]) -> bool:
    assert EBOOK_CONVERT is not None
    result = subprocess.run(
        [EBOOK_CONVERT, str(src), str(dst), *extra_args],
        capture_output=True,
        timeout=120,
    )
    if result.returncode == 0:
        return True

    print(red(f"  FAIL: {result.stderr.decode()[:300]}"))
    return False


def main() -> None:
    if not EBOOK_CONVERT:
        print(red("ERROR: ebook-convert not found on PATH"), file=sys.stderr)
        sys.exit(1)

    if not INPUT.exists():
        print(red(f"ERROR: input file not found: {INPUT}"), file=sys.stderr)
        sys.exit(1)

    catalog = json.loads(CATALOG.read_text())
    output_formats = sorted(f for f in catalog["output_plugins"])

    OUTPUT.mkdir(exist_ok=True)

    ok: list[str] = []
    failed: list[str] = []

    print(f"Converting {INPUT.name} → {len(output_formats)} formats...\n")
    for fmt in output_formats:
        dst = OUTPUT / f"book.{fmt}"
        extra = _feature_flags(fmt, catalog)
        print(f"  {fmt} ({len(extra)} extra flags)...", end=" ", flush=True)
        if calibre_convert(INPUT, dst, extra):
            print(green("OK"))
            ok.append(fmt)
        else:
            failed.append(fmt)

    print(f"\n{cyan('=' * 50)}")
    status = (
        f"DONE: {green(str(len(ok)))} OK, {red(str(len(failed))) if failed else dim('0')} failed"
    )
    print(status)
    if ok:
        print(f"\n{green(f'OK ({len(ok)})')}: {', '.join(ok)}")
    if failed:
        print(f"\n{red(f'Failed ({len(failed)})')}: {', '.join(failed)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
