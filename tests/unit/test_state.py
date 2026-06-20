"""Cover app.state: accessors, the not-initialised guards, and reset_executor."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

import pytest

from app import state


def test_get_executor_uninitialised(monkeypatch):
    monkeypatch.setattr(state, "_executor", None)
    with pytest.raises(RuntimeError, match="executor not initialised"):
        state.get_executor()


def test_get_semaphore_uninitialised(monkeypatch):
    monkeypatch.setattr(state, "_semaphore", None)
    with pytest.raises(RuntimeError, match="semaphore not initialised"):
        state.get_semaphore()


def test_set_and_get_executor(monkeypatch):
    ex = ProcessPoolExecutor(max_workers=1)
    monkeypatch.setattr(state, "_executor", None)
    state.set_executor(ex)
    assert state.get_executor() is ex
    ex.shutdown()


def test_reset_executor_replaces_and_shuts_down_old(monkeypatch):
    monkeypatch.setattr(state, "ProcessPoolExecutor", ThreadPoolExecutor)
    old = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(state, "_executor", old)

    state.reset_executor()
    assert state.get_executor() is not old  # rebuilt
    assert old._shutdown  # old pool was shut down


def test_reset_executor_noop_when_broken_is_stale(monkeypatch):
    monkeypatch.setattr(state, "ProcessPoolExecutor", ThreadPoolExecutor)
    current = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(state, "_executor", current)

    # broken refers to some *other* (already-replaced) executor → no-op.
    state.reset_executor(broken=ProcessPoolExecutor(max_workers=1))
    assert state.get_executor() is current
    current.shutdown()


def test_reset_executor_from_none(monkeypatch):
    monkeypatch.setattr(state, "ProcessPoolExecutor", ThreadPoolExecutor)
    monkeypatch.setattr(state, "_executor", None)
    state.reset_executor()
    assert state.get_executor() is not None
