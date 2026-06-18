"""Calibre Plumber wrapper — runs synchronously inside a ProcessPoolExecutor worker.

No FastAPI or asyncio imports here. Calibre modules are imported lazily so they
are loaded once per worker process rather than on every call.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.utils.errors import ConversionError


def convert(input_path: str, output_path: str, opts: SimpleNamespace) -> None:
    try:
        from calibre.ebooks.conversion.plumber import Plumber
        from calibre.utils.logging import Log
    except ImportError as exc:
        raise ConversionError(
            f"Calibre not found in PYTHONPATH. Is PYTHONPATH=/usr/local/lib set? ({exc})"
        ) from exc

    log = Log()
    try:
        plumber = Plumber(input_path, output_path, log)
        plumber.merge_ui_recommendations(vars(opts))
        plumber.run()
    except Exception as exc:
        raise ConversionError(str(exc)) from exc
