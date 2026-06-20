#!/usr/bin/env python3
"""
Discover which files/directories in /opt/calibre are unused by ebook-convert
so they can be deleted in the Dockerfile to reduce image size.

Run INSIDE the Docker container (repo bind-mounted at /app):

    python /app/scripts/prune_calibre.py [--py]

Strategy: try to remove entire directories first (largest first). If a
directory must be kept, descend into it and repeat — subdirectories before
files. This finds the coarsest removable units first, minimising test runs.

Options:
    --py    Also test .py/.pyc files (skipped by default; they are numerous,
            individually small, and almost all required by the pipeline)

Ctrl-C at any time — results found so far are printed in the summary.
"""

from __future__ import annotations

import argparse
import itertools
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CALIBRE_DIR = Path("/opt/calibre")
EBOOK_CONVERT = CALIBRE_DIR / "ebook-convert"

REPO_ROOT = Path(__file__).parents[1]
TEST_SCRIPT = REPO_ROOT / "tests" / "epub-test" / "test.py"
TEST_INPUT = REPO_ROOT / "tests" / "epub-test" / "book.epub"


def run_test() -> bool:
    result = subprocess.run(
        [sys.executable, str(TEST_SCRIPT)],
        capture_output=True,
        timeout=300,
    )
    return result.returncode == 0


def _path_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def _children_sorted(directory: Path) -> list[Path]:
    """Directories largest-first, then files largest-first."""
    dirs = sorted(
        (p for p in directory.iterdir() if p.is_dir()),
        key=_path_size,
        reverse=True,
    )
    files = sorted(
        (p for p in directory.iterdir() if p.is_file()),
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    return dirs + files


def prune(
    path: Path,
    tmp: Path,
    id_gen: itertools.count[int],
    skip_py: bool,
    safe: list[tuple[Path, int]],
    file_counter: list[int],
    file_total: int,
) -> None:
    """Try to remove path. If it is a kept directory, recurse into it."""
    rel = path.relative_to(CALIBRE_DIR)
    is_dir = path.is_dir()

    if not is_dir:
        if path == EBOOK_CONVERT:
            return
        if skip_py and path.suffix in {".py", ".pyc"}:
            return
        file_counter[0] += 1

    size = _path_size(path)
    label = f"{rel}{'/' if is_dir else ''}"
    tag = "dir" if is_dir else f"{file_counter[0]}/{file_total}"

    backup = tmp / str(next(id_gen))
    if is_dir:
        shutil.copytree(path, backup, symlinks=True)
        shutil.rmtree(path)
    else:
        shutil.copy2(path, backup)
        path.unlink()

    try:
        passed = run_test()
    except subprocess.TimeoutExpired:
        passed = False

    if passed:
        print(f"[{tag}] SAFE  {label}  ({size:,} B)")
        safe.append((rel, size))
        if backup.is_dir():
            shutil.rmtree(backup, ignore_errors=True)
        else:
            backup.unlink(missing_ok=True)
    else:
        if is_dir:
            shutil.copytree(backup, path, symlinks=True)
            shutil.rmtree(backup)
            print(f"[dir]  KEEP  {label}  — descending")
            for child in _children_sorted(path):
                prune(child, tmp, id_gen, skip_py, safe, file_counter, file_total)
        else:
            shutil.copy2(backup, path)
            backup.unlink(missing_ok=True)
            print(f"[{tag}] KEEP  {label}")


def print_summary(safe: list[tuple[Path, int]]) -> None:
    total = sum(s for _, s in safe)
    print(f"\n{'=' * 60}")
    print(f"SAFE to delete: {len(safe)} entries  ({total / 1_048_576:.1f} MB)")
    for rel, size in safe:
        print(f"  {rel}  ({size:,} B)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--py", action="store_true", help="Also test .py/.pyc files")
    args = parser.parse_args()

    for path, label in [
        (CALIBRE_DIR, "/opt/calibre"),
        (EBOOK_CONVERT, "ebook-convert binary"),
        (TEST_SCRIPT, "epub test script"),
        (TEST_INPUT, "test epub input"),
    ]:
        if not path.exists():
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            sys.exit(1)

    skip_py = not args.py
    skip_suffixes = {".py", ".pyc"} if skip_py else set()
    file_total = sum(
        1
        for f in CALIBRE_DIR.rglob("*")
        if f.is_file() and f != EBOOK_CONVERT and f.suffix not in skip_suffixes
    )

    print(f"Files to check: {file_total}  (directories tried as units first)")
    print("Running baseline test...")
    if not run_test():
        print("ERROR: baseline test failed before any files were removed", file=sys.stderr)
        sys.exit(1)
    print("Baseline OK.\n")

    safe: list[tuple[Path, int]] = []
    file_counter = [0]

    with tempfile.TemporaryDirectory(prefix="calibre_prune_") as tmp:
        id_gen: itertools.count[int] = itertools.count()
        try:
            for child in _children_sorted(CALIBRE_DIR):
                prune(child, Path(tmp), id_gen, skip_py, safe, file_counter, file_total)
        except KeyboardInterrupt:
            print("\nInterrupted.")

    print_summary(safe)


if __name__ == "__main__":
    main()
