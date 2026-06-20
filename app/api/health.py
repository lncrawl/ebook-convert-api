from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..config import settings
from ..core.introspector import calibre_version

router = APIRouter()


@router.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "calibre_version": calibre_version(),
            "max_concurrent_jobs": settings.max_concurrent_jobs,
        }
    )


@router.get("/ready")
async def ready() -> JSONResponse:
    return JSONResponse({"status": "ready"})
