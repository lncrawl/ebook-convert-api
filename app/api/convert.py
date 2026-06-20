from __future__ import annotations

import asyncio
import zipfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app import state
from app.config import settings
from app.core import introspector, options_schema
from app.core.converter import convert
from app.core.formats import MIME_TYPES
from app.core.options_builder import build_cli_args
from app.utils.tempfiles import ConversionTempDir

router = APIRouter()

_MAX_UPLOAD_BYTES = settings.max_upload_mb * 1024 * 1024


async def convert_file(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    output_format: str,
    **options: object,
) -> FileResponse:
    # Detect input format from upload filename
    suffix = Path(file.filename or "").suffix.lstrip(".").lower()
    if not suffix or suffix not in introspector.input_formats():
        raise HTTPException(
            status_code=400,
            detail=f"Cannot determine a supported input format from filename {file.filename!r}. "
            f"Rename the file to include a supported extension.",
        )

    # output_format is already constrained to the supported set by the enum annotation.
    output_format = output_format.lower()

    # Keep only options the user actually set, and only those valid for this format pair —
    # the form exposes the union of all options, but Calibre rejects cross-format flags.
    metadata = introspector.options_by_name(suffix, output_format)
    opts_dict = {k: v for k, v in options.items() if v is not None and k in metadata}

    cli_args = build_cli_args(opts_dict, metadata)

    # Check semaphore without blocking — 503 immediately if all workers busy
    semaphore = state.get_semaphore()
    if semaphore.locked() and semaphore._value == 0:  # type: ignore[attr-defined]
        raise HTTPException(
            status_code=503,
            detail="All conversion workers are busy. Retry after a moment.",
            headers={"Retry-After": "5"},
        )

    tmp = ConversionTempDir()
    tmp_path = tmp.__enter__()

    try:
        # Stream upload into temp dir, enforcing size limit
        input_path = tmp_path / f"input.{suffix}"
        bytes_read = 0
        with input_path.open("wb") as fh:
            while chunk := await file.read(1024 * 64):
                bytes_read += len(chunk)
                if bytes_read > _MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Upload exceeds {settings.max_upload_mb} MB limit.",
                    )
                fh.write(chunk)

        output_path = tmp_path / f"output.{output_format}"

        async with semaphore:
            loop = asyncio.get_event_loop()
            try:
                await asyncio.wait_for(
                    loop.run_in_executor(
                        state.get_executor(),
                        convert,
                        str(input_path),
                        str(output_path),
                        cli_args,
                    ),
                    timeout=float(settings.conversion_timeout_seconds),
                )
            except TimeoutError as exc:
                raise HTTPException(
                    status_code=504,
                    detail=f"Conversion timed out after {settings.conversion_timeout_seconds}s",
                ) from exc
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Some output formats (e.g. oeb) write a directory of files rather than a
        # single file. Pack the directory into a ZIP so FileResponse can serve it.
        if output_path.is_dir():
            packed = output_path.parent / f"output.{output_format}.zip"
            with zipfile.ZipFile(packed, "w", zipfile.ZIP_DEFLATED) as zf:
                for child in sorted(output_path.rglob("*")):
                    if child.is_file():
                        zf.write(child, child.relative_to(output_path))
            output_path = packed

        if not output_path.exists():
            raise HTTPException(status_code=500, detail="Conversion produced no output file")

        media_type = MIME_TYPES.get(output_format, "application/octet-stream")
        stem = Path(file.filename or "converted").stem
        download_name = f"{stem}.{output_format}"

        background_tasks.add_task(_cleanup, tmp)

        return FileResponse(
            path=str(output_path),
            media_type=media_type,
            filename=download_name,
        )

    except HTTPException:
        tmp.__exit__(None, None, None)
        raise
    except Exception as exc:
        tmp.__exit__(None, None, None)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _cleanup(tmp: ConversionTempDir) -> None:
    tmp.__exit__(None, None, None)


# Replace the placeholder signature with one field per catalog option so FastAPI
# renders each as a typed multipart form field in the Swagger docs.
convert_file.__signature__ = options_schema.convert_signature()  # type: ignore[attr-defined]
router.post("/convert")(convert_file)
