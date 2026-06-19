import re
import subprocess

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "calibre_version": _calibre_version(),
            "max_concurrent_jobs": settings.max_concurrent_jobs,
        }
    )


@router.get("/ready")
async def ready() -> JSONResponse:
    return JSONResponse({"status": "ready"})


def _calibre_version() -> str:
    try:
        result = subprocess.run(
            ["ebook-convert", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        match = re.search(r"calibre\s+(\S+)", result.stdout or result.stderr)
        return match.group(1) if match else "unknown"
    except Exception:
        return "unknown"
