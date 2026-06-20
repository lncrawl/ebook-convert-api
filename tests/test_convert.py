"""Conversion integration tests: POST /convert against a live container."""

from __future__ import annotations

import json

import httpx
import pytest

from tests.conftest import INPUT_FIXTURES, OUTPUT_FORMATS


# ---------------------------------------------------------------------------
# EPUB → every supported output format
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("out_fmt", OUTPUT_FORMATS)
def test_epub_to_output_format(
    client: httpx.Client,
    epub_fixture: tuple[str, bytes],
    out_fmt: str,
) -> None:
    filename, data = epub_fixture
    resp = client.post(
        "/convert",
        files={"file": (filename, data, "application/epub+zip")},
        data={"output_format": out_fmt},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.content) > 0
    cd = resp.headers.get("content-disposition", "")
    assert f".{out_fmt}" in cd


# ---------------------------------------------------------------------------
# Every input format we have a fixture for → EPUB
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("in_fmt", [f for f in INPUT_FIXTURES if f != "epub"])
def test_input_format_to_epub(client: httpx.Client, in_fmt: str) -> None:
    filename, data = INPUT_FIXTURES[in_fmt]
    resp = client.post(
        "/convert",
        files={"file": (filename, data, "application/octet-stream")},
        data={"output_format": "epub"},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.content) > 0


# ---------------------------------------------------------------------------
# Conversion options
# ---------------------------------------------------------------------------


def test_conversion_with_options(
    client: httpx.Client,
    epub_fixture: tuple[str, bytes],
) -> None:
    filename, data = epub_fixture
    options = json.dumps({"margin_top": 36, "margin_bottom": 36, "base_font_size": 12})
    resp = client.post(
        "/convert",
        files={"file": (filename, data, "application/epub+zip")},
        data={"output_format": "epub", "options": options},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.content) > 0


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_unsupported_output_format(
    client: httpx.Client,
    epub_fixture: tuple[str, bytes],
) -> None:
    filename, data = epub_fixture
    resp = client.post(
        "/convert",
        files={"file": (filename, data, "application/epub+zip")},
        data={"output_format": "xyz_bogus"},
    )
    assert resp.status_code == 400


def test_unrecognized_input_filename(client: httpx.Client) -> None:
    resp = client.post(
        "/convert",
        files={"file": ("book.xyz_bogus", b"irrelevant", "application/octet-stream")},
        data={"output_format": "epub"},
    )
    assert resp.status_code == 400


def test_invalid_options_json(
    client: httpx.Client,
    epub_fixture: tuple[str, bytes],
) -> None:
    filename, data = epub_fixture
    resp = client.post(
        "/convert",
        files={"file": (filename, data, "application/epub+zip")},
        data={"output_format": "epub", "options": "not-json"},
    )
    assert resp.status_code == 422


def test_options_must_be_object(
    client: httpx.Client,
    epub_fixture: tuple[str, bytes],
) -> None:
    filename, data = epub_fixture
    resp = client.post(
        "/convert",
        files={"file": (filename, data, "application/epub+zip")},
        data={"output_format": "epub", "options": "[1, 2, 3]"},
    )
    assert resp.status_code == 422
