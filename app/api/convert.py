from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app import state
from app.config import settings
from app.core.converter import convert
from app.core.formats import INPUT_FORMATS, MIME_TYPES, OUTPUT_FORMATS
from app.core.options_builder import build_plumber_options
from app.models.options_universal import ConversionOptions
from app.utils.tempfiles import ConversionTempDir

router = APIRouter()

_MAX_UPLOAD_BYTES = settings.max_upload_mb * 1024 * 1024


@router.post("/convert")
async def convert_file(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    output_format: str = Form(...),
    options: str = Form(default="{}"),
) -> FileResponse:
    output_format = output_format.lower().lstrip(".")
    if output_format not in OUTPUT_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported output format: {output_format!r}")

    # Detect input format from upload filename
    suffix = Path(file.filename or "").suffix.lstrip(".").lower()
    if not suffix or suffix not in INPUT_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot determine input format from filename {file.filename!r}. "
                   f"Rename the file to include a supported extension.",
        )

    # Parse and validate options
    try:
        opts_data = json.loads(options)
        conv_options = ConversionOptions.model_validate(opts_data)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid options JSON: {exc}") from exc

    plumber_opts = build_plumber_options(conv_options)

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
                        plumber_opts,
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
