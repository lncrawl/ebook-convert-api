"""Shared fixtures for integration tests.

All tests target a live HTTP server.  Set API_BASE_URL to point at it
(default: http://localhost:8000).  The entire test session is skipped if
the server is not reachable.
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path

import httpx
import pytest

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Load format lists from the committed catalog so we can parametrize without
# hitting the server at collection time.
_CATALOG_PATH = Path(__file__).parent.parent / "data" / "catalog.json"
_catalog = json.loads(_CATALOG_PATH.read_text())
INPUT_FORMATS: list[str] = sorted(_catalog["input_plugins"])
OUTPUT_FORMATS: list[str] = sorted(_catalog["output_plugins"])


# ---------------------------------------------------------------------------
# Session-scoped client — skip entire session if server is down
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def client() -> httpx.Client:
    try:
        with httpx.Client(base_url=BASE_URL, timeout=10.0) as probe:
            resp = probe.get("/ready")
            resp.raise_for_status()
    except Exception as exc:
        pytest.skip(f"API server not reachable at {BASE_URL}: {exc}")

    with httpx.Client(base_url=BASE_URL, timeout=180.0) as c:
        yield c


# ---------------------------------------------------------------------------
# Minimal ebook fixtures
# ---------------------------------------------------------------------------


def _epub_bytes() -> bytes:
    """Return a tiny but valid EPUB 2 file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # mimetype: first entry, uncompressed, no extra fields
        mi = zipfile.ZipInfo("mimetype")
        mi.compress_type = zipfile.ZIP_STORED
        zf.writestr(mi, "application/epub+zip")

        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            "  <rootfiles>"
            '    <rootfile full-path="OEBPS/content.opf"'
            '              media-type="application/oebps-package+xml"/>'
            "  </rootfiles>"
            "</container>",
        )
        zf.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0" encoding="utf-8"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uid">'
            '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "    <dc:title>Test Book</dc:title>"
            "    <dc:creator>Test Author</dc:creator>"
            '    <dc:identifier id="uid">test-001</dc:identifier>'
            "    <dc:language>en</dc:language>"
            "  </metadata>"
            "  <manifest>"
            '    <item id="ncx"  href="toc.ncx"      media-type="application/x-dtbncx+xml"/>'
            '    <item id="ch1"  href="chapter1.xhtml" media-type="application/xhtml+xml"/>'
            "  </manifest>"
            '  <spine toc="ncx"><itemref idref="ch1"/></spine>'
            "</package>",
        )
        zf.writestr(
            "OEBPS/toc.ncx",
            '<?xml version="1.0" encoding="utf-8"?>'
            "<!DOCTYPE ncx PUBLIC"
            ' "-//NISO//DTD ncx 2005-1//EN"'
            ' "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">'
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
            '  <head><meta name="dtb:uid" content="test-001"/></head>'
            "  <docTitle><text>Test Book</text></docTitle>"
            "  <navMap>"
            '    <navPoint id="np1" playOrder="1">'
            "      <navLabel><text>Chapter 1</text></navLabel>"
            '      <content src="chapter1.xhtml"/>'
            "    </navPoint>"
            "  </navMap>"
            "</ncx>",
        )
        zf.writestr(
            "OEBPS/chapter1.xhtml",
            '<?xml version="1.0" encoding="utf-8"?>'
            "<!DOCTYPE html PUBLIC"
            ' "-//W3C//DTD XHTML 1.1//EN"'
            ' "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">'
            '<html xmlns="http://www.w3.org/1999/xhtml">'
            "  <head><title>Chapter 1</title></head>"
            "  <body>"
            "    <h1>Chapter 1</h1>"
            "    <p>This is a minimal test ebook used for integration testing.</p>"
            "    <p>It contains enough structure for Calibre to convert successfully.</p>"
            "  </body>"
            "</html>",
        )
    return buf.getvalue()


def _htmlz_bytes() -> bytes:
    """Return a minimal HTMLZ (zipped HTML) file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "index.html",
            "<!DOCTYPE html><html><head><title>Test</title></head>"
            "<body><h1>Test Book</h1><p>Integration test fixture.</p></body></html>",
        )
        zf.writestr(
            "metadata.opf",
            '<?xml version="1.0" encoding="utf-8"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uid">'
            '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "    <dc:title>Test Book</dc:title>"
            '    <dc:identifier id="uid">test-htmlz-001</dc:identifier>'
            "    <dc:language>en</dc:language>"
            "  </metadata>"
            "</package>",
        )
    return buf.getvalue()


def _txtz_bytes() -> bytes:
    """Return a minimal TXTZ (zipped plain text) file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("index.txt", "Test Book\n\nThis is a minimal test ebook fixture.\n")
    return buf.getvalue()


def _fb2_bytes() -> bytes:
    return (
        b'<?xml version="1.0" encoding="utf-8"?>'
        b'<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"'
        b' xmlns:l="http://www.w3.org/1999/xlink">'
        b"  <description>"
        b"    <title-info>"
        b"      <genre>prose_contemporary</genre>"
        b"      <author><first-name>Test</first-name><last-name>Author</last-name></author>"
        b"      <book-title>Test Book</book-title>"
        b"      <lang>en</lang>"
        b"    </title-info>"
        b"  </description>"
        b"  <body>"
        b"    <section>"
        b"      <title><p>Chapter 1</p></title>"
        b"      <p>This is a minimal test ebook used for integration testing.</p>"
        b"    </section>"
        b"  </body>"
        b"</FictionBook>"
    )


def _rtf_bytes() -> bytes:
    return (
        rb"{\rtf1\ansi\deff0"
        rb"{\fonttbl{\f0 Times New Roman;}}"
        rb"\f0\fs24 Test Book\par"
        rb"This is a minimal integration test fixture.\par"
        rb"}"
    )


# Map: extension → (filename, bytes)
INPUT_FIXTURES: dict[str, tuple[str, bytes]] = {
    "epub": ("book.epub", _epub_bytes()),
    "txt": ("book.txt", b"Test Book\n\nThis is a minimal integration test fixture.\n"),
    "text": ("book.text", b"Test Book\n\nThis is a minimal integration test fixture.\n"),
    "html": (
        "book.html",
        b"<!DOCTYPE html><html><head><title>Test</title></head>"
        b"<body><h1>Test Book</h1><p>Integration test fixture.</p></body></html>",
    ),
    "htm": (
        "book.htm",
        b"<!DOCTYPE html><html><head><title>Test</title></head>"
        b"<body><h1>Test Book</h1><p>Integration test fixture.</p></body></html>",
    ),
    "xhtml": (
        "book.xhtml",
        b'<?xml version="1.0" encoding="utf-8"?>'
        b'<html xmlns="http://www.w3.org/1999/xhtml">'
        b"<head><title>Test</title></head>"
        b"<body><h1>Test Book</h1><p>Integration test fixture.</p></body>"
        b"</html>",
    ),
    "xhtm": (
        "book.xhtm",
        b'<?xml version="1.0" encoding="utf-8"?>'
        b'<html xmlns="http://www.w3.org/1999/xhtml">'
        b"<head><title>Test</title></head>"
        b"<body><h1>Test Book</h1><p>Integration test fixture.</p></body>"
        b"</html>",
    ),
    "shtml": (
        "book.shtml",
        b"<!DOCTYPE html><html><head><title>Test</title></head>"
        b"<body><h1>Test Book</h1><p>Integration test fixture.</p></body></html>",
    ),
    "shtm": (
        "book.shtm",
        b"<!DOCTYPE html><html><head><title>Test</title></head>"
        b"<body><h1>Test Book</h1><p>Integration test fixture.</p></body></html>",
    ),
    "markdown": ("book.markdown", b"# Test Book\n\nThis is a minimal integration test fixture.\n"),
    "md": ("book.md", b"# Test Book\n\nThis is a minimal integration test fixture.\n"),
    "textile": (
        "book.textile",
        b"h1. Test Book\n\nThis is a minimal integration test fixture.\n",
    ),
    "rtf": ("book.rtf", _rtf_bytes()),
    "fb2": ("book.fb2", _fb2_bytes()),
    "htmlz": ("book.htmlz", _htmlz_bytes()),
    "txtz": ("book.txtz", _txtz_bytes()),
}


@pytest.fixture(scope="session")
def epub_fixture() -> tuple[str, bytes]:
    return INPUT_FIXTURES["epub"]
