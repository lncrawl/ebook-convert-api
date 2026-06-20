"""In-process unit-test fixtures.

These tests instrument `app` directly with `TestClient` (so coverage is measured)
and never touch a real Calibre binary: conversions run in a thread pool and the
`convert` worker function is monkeypatched per test.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

import app.api.convert as convert_mod
import app.main as main_mod
import app.state as state_mod


@pytest.fixture(autouse=True)
def use_thread_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    # Run conversions in threads, not processes: keeps tests in-process, needs no
    # real Calibre, and lets us monkeypatch the `convert` function per test.
    monkeypatch.setattr(main_mod, "ProcessPoolExecutor", ThreadPoolExecutor)
    monkeypatch.setattr(state_mod, "ProcessPoolExecutor", ThreadPoolExecutor)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(main_mod.create_app()) as c:
        yield c


@pytest.fixture
def set_convert(monkeypatch: pytest.MonkeyPatch) -> Callable[[Callable], None]:
    """Replace the `convert` worker the endpoint calls with a fake implementation."""

    def _set(impl: Callable) -> None:
        monkeypatch.setattr(convert_mod, "convert", impl)

    return _set
