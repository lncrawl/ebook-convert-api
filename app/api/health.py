from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    calibre_version = _calibre_version()
    return JSONResponse(
        {
            "status": "ok",
            "calibre_version": calibre_version,
            "max_concurrent_jobs": settings.max_concurrent_jobs,
        }
    )


@router.get("/ready")
async def ready() -> JSONResponse:
    return JSONResponse({"status": "ready"})


def _calibre_version() -> str:
    try:
        from calibre.constants import numeric_version

        return ".".join(str(v) for v in numeric_version)
    except Exception:
        return "unknown"
