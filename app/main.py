from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from concurrent.futures import ProcessPoolExecutor
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import state
from app.api import convert, formats, health
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    executor = ProcessPoolExecutor(max_workers=settings.max_concurrent_jobs)
    semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
    state.set_executor(executor)
    state.set_semaphore(semaphore)
    try:
        yield
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def create_app() -> FastAPI:
    app = FastAPI(
        title="ebook-convert-api",
        description="HTTP API wrapping Calibre's ebook-convert pipeline",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.use_auth:
        from app.middleware.auth import AuthMiddleware

        app.add_middleware(AuthMiddleware)

    app.include_router(health.router)
    app.include_router(formats.router)
    app.include_router(convert.router)

    return app


app = create_app()
