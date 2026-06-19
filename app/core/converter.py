"""Calls ebook-convert CLI in a subprocess. Runs inside a ProcessPoolExecutor worker."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

from app.utils.errors import ConversionError


def convert(input_path: str, output_path: str, opts: SimpleNamespace) -> None:
    cmd = ["ebook-convert", input_path, output_path, *_opts_to_args(opts)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise ConversionError("ebook-convert not found — is Calibre installed?") from exc

    if result.returncode != 0:
        raise ConversionError(result.stderr or result.stdout or "ebook-convert failed")


def _opts_to_args(opts: SimpleNamespace) -> list[str]:
    args: list[str] = []
    for key, value in vars(opts).items():
        flag = "--" + key.replace("_", "-")
        if value is True:
            args.append(flag)
        elif value is False or value is None:
            pass
        else:
            args.extend([flag, str(value)])
    return args
