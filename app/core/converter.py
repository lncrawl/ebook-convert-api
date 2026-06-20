"""Calls ebook-convert CLI in a subprocess. Runs inside a ProcessPoolExecutor worker."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from app.utils.errors import ConversionError


def convert(input_path: str, output_path: str, args: list[str]) -> None:
    cmd = ["ebook-convert", input_path, output_path, *args]
    home = tempfile.mkdtemp(prefix="ebook-convert-home-")
    env = {**os.environ, "HOME": home}
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    except FileNotFoundError as exc:
        raise ConversionError("ebook-convert not found — is Calibre installed?") from exc
    finally:
        shutil.rmtree(home, ignore_errors=True)

    if result.returncode != 0:
        raise ConversionError(result.stderr or result.stdout or "ebook-convert failed")
