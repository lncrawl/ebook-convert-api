from __future__ import annotations

import asyncio
import zipfile
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.datastructures import UploadFile as StarletteUploadFile

from .. import state
from ..config import settings
from ..core import introspector, options_schema
from ..core.converter import convert
from ..core.formats import MIME_TYPES
from ..core.options_builder import FILE_OPTIONS, build_cli_args
from ..models.introspection import OptionMetadata
from ..utils.tempfiles import ConversionTempDir

router = APIRouter()

_MAX_UPLOAD_BYTES = settings.max_upload_mb * 1024 * 1024


def _partition_options(
    options: dict[str, object],
    metadata: dict[str, OptionMetadata],
) -> tuple[dict[str, object], dict[str, StarletteUploadFile]]:
    """Split submitted options into scalar values and file uploads.

    Only options the user actually set and that are valid for this format pair
    are kept (the form exposes the union of all options, but Calibre rejects
    cross-format flags). File-path options must arrive as an actual upload; a
    stray non-upload value (e.g. a string path) is dropped so a caller can't
    point the flag at a server-side path. (The multipart parser yields
    Starlette's UploadFile, of which FastAPI's is a subclass — match the base.)
    """
    opts_dict: dict[str, object] = {}
    file_uploads: dict[str, StarletteUploadFile] = {}
    for name, value in options.items():
        if value is None or name not in metadata:
            continue
        if name in FILE_OPTIONS:
            if isinstance(value, StarletteUploadFile) and value.filename:
                file_uploads[name] = value
        else:
            opts_dict[name] = value
    return opts_dict, file_uploads


async def _save_upload(upload: StarletteUploadFile, dest: Path) -> None:
    """Stream an upload to ``dest``, enforcing the global per-file size limit."""
    bytes_read = 0
    with dest.open("wb") as fh:
        while chunk := await upload.read(1024 * 64):
            bytes_read += len(chunk)
            if bytes_read > _MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Upload exceeds {settings.max_upload_mb} MB limit.",
                )
            fh.write(chunk)


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

    metadata = introspector.options_by_name(suffix, output_format)
    opts_dict, file_uploads = _partition_options(options, metadata)

    # Check semaphore without blocking — 503 immediately if all workers busy
    # (Semaphore.locked() is True exactly when no permits remain).
    semaphore = state.get_semaphore()
    if semaphore.locked():
        raise HTTPException(
            status_code=503,
            detail="All conversion workers are busy. Retry after a moment.",
            headers={"Retry-After": "5"},
        )

    tmp = ConversionTempDir()
    tmp_path = tmp.__enter__()

    try:
        # Stream the main upload into the temp dir, enforcing the size limit.
        input_path = tmp_path / f"input.{suffix}"
        await _save_upload(file, input_path)

        # Save any file-path option uploads alongside it and point the flag at the
        # saved path (keeping the original suffix, which Calibre uses e.g. to
        # detect the cover's image type).
        for name, upload in file_uploads.items():
            dest = tmp_path / f"opt-{name}{Path(upload.filename or '').suffix}"
            await _save_upload(upload, dest)
            opts_dict[name] = str(dest)

        cli_args = build_cli_args(opts_dict, metadata)

        output_path = tmp_path / f"output.{output_format}"

        async with semaphore:
            loop = asyncio.get_running_loop()
            executor = state.get_executor()
            try:
                await asyncio.wait_for(
                    loop.run_in_executor(
                        executor,
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
            except BrokenProcessPool as exc:
                # A worker crashed (e.g. OOM/segfault), poisoning the pool. Rebuild
                # it so the service recovers instead of failing every later request.
                state.reset_executor(broken=executor)
                raise HTTPException(
                    status_code=503,
                    detail="A conversion worker crashed; the pool was reset. Please retry.",
                    headers={"Retry-After": "2"},
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
