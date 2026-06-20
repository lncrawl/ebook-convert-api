"""
Shared process-pool executor and concurrency semaphore.

Lives in its own module to break the circular import that would arise if
app/main.py (which owns the lifespan) and app/api/convert.py (which needs
the executor) both imported each other.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor

from .config import settings

_executor: ProcessPoolExecutor | None = None
_semaphore: asyncio.Semaphore | None = None


def set_executor(executor: ProcessPoolExecutor) -> None:
    global _executor
    _executor = executor


def reset_executor(broken: ProcessPoolExecutor | None = None) -> None:
    """Replace the process pool after a worker crash (BrokenProcessPool).

    A single crashed worker poisons the whole ProcessPoolExecutor — every later
    submit raises BrokenProcessPool until the pool is rebuilt. ``broken`` guards
    against concurrent requests each rebuilding: only the request whose executor
    is still the current one performs the swap.
    """
    global _executor
    if broken is not None and _executor is not broken:
        return
    old = _executor
    _executor = ProcessPoolExecutor(max_workers=settings.max_concurrent_jobs)
    if old is not None:
        old.shutdown(wait=False, cancel_futures=True)


def set_semaphore(semaphore: asyncio.Semaphore) -> None:
    global _semaphore
    _semaphore = semaphore


def get_executor() -> ProcessPoolExecutor:
    if _executor is None:
        raise RuntimeError("executor not initialised — app lifespan not running")
    return _executor


def get_semaphore() -> asyncio.Semaphore:
    if _semaphore is None:
        raise RuntimeError("semaphore not initialised — app lifespan not running")
    return _semaphore
