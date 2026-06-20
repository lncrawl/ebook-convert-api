"""Tests for the non-conversion endpoints: /ready, /health, /formats, /formats/options."""

from __future__ import annotations

import httpx
import pytest

from .conftest import INPUT_FORMATS, OUTPUT_FORMATS


def test_ready(client: httpx.Client) -> None:
    resp = client.get("/ready")
    assert resp.status_code == 200


def test_health(client: httpx.Client) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "calibre_version" in body
    assert "max_concurrent_jobs" in body


def test_formats_match_catalog(client: httpx.Client) -> None:
    resp = client.get("/formats")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["input_formats"]) == set(INPUT_FORMATS)
    assert set(body["output_formats"]) == set(OUTPUT_FORMATS)


@pytest.mark.parametrize("out_fmt", OUTPUT_FORMATS)
def test_options_epub_to_output(client: httpx.Client, out_fmt: str) -> None:
    resp = client.get(f"/formats/epub/{out_fmt}/options")
    assert resp.status_code == 200
    groups = resp.json()
    assert isinstance(groups, list)
    assert len(groups) > 0
    for g in groups:
        assert "group" in g
        assert "options" in g
        assert isinstance(g["options"], list)
        assert len(g["options"]) > 0


def test_options_invalid_input_format(client: httpx.Client) -> None:
    resp = client.get("/formats/bogus/epub/options")
    assert resp.status_code == 404


def test_options_invalid_output_format(client: httpx.Client) -> None:
    resp = client.get("/formats/epub/bogus/options")
    assert resp.status_code == 404
