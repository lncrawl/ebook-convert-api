#!/usr/bin/env python3
"""Generate sample fixture files for all supported Calibre input formats.

Run from the repo root:
    python tests/fixtures/generate.py

Requires Calibre's ebook-convert to be on PATH
"""

from __future__ import annotations

import base64
import io
import json
import os
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

FIXTURES = Path(__file__).parent
REPO_ROOT = Path(__file__).parent.parent.parent
CATALOG = REPO_ROOT / "data" / "catalog.json"
EPUB_TEST = Path(__file__).parent.parent / "epub-test" / "book.epub"

# Output formats used when testing each input fixture.
# Formats skipped during cross-format testing (beyond the generator's SKIPPED set).
_TEST_SKIP = {
    "recipe",
    "downloaded_recipe",
}

if not CATALOG.exists():
    print(f"ERROR: catalog not found: {CATALOG}", file=sys.stderr)
    sys.exit(1)

catalog = json.loads(CATALOG.read_text())
input_formats = set(catalog["input_plugins"].keys())
output_formats = sorted(catalog["output_plugins"].keys())

# ---------------------------------------------------------------------------
# Console Color
# ---------------------------------------------------------------------------


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text


def green(t: str) -> str:
    return _c("32", t)


def yellow(t: str) -> str:
    return _c("33", t)


def red(t: str) -> str:
    return _c("31", t)


def cyan(t: str) -> str:
    return _c("36", t)


def bold(t: str) -> str:
    return _c("1", t)


def dim(t: str) -> str:
    return _c("2", t)


# ---------------------------------------------------------------------------
# Synthetic generators for text/zip-based formats
# ---------------------------------------------------------------------------


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


def _fbz_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("book.fb2", _fb2_bytes())
    return buf.getvalue()


def _htmlz_bytes() -> bytes:
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
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("index.txt", "Test Book\n\nThis is a minimal test ebook fixture.\n")
    return buf.getvalue()


def _minimal_png() -> bytes:
    """1x1 white PNG."""
    import zlib

    raw = b"\x00\xff\xff\xff"
    compressed = zlib.compress(raw)

    def chunk(tag: bytes, data: bytes) -> bytes:
        import struct

        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return length + tag + data + crc

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


def _cbz_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("page001.png", _minimal_png())
    return buf.getvalue()


# Minimal 7z archive containing one 1x1 white PNG at the archive root.
# Generated once with py7zr and embedded so no runtime dependency is needed.
_CB7_B64 = (
    "N3q8ryccAARibmLkqAAAAAAAAAAUAAAAAAAAAB8jtWIBAESJUE5HDQoaCgAAAA1JSERSAAAAAQAAAAEIAgAA"
    "AJB3U94AAAAMSURBVHicY/j//z8ABf4C/g3vRrgAAAAASUVORK5CYIIA4ABcAFddAACBMweuD9JnHT1A"
    "u5RkHH7rYmP2uZeSKtq1WfsscrQeY0rxONoyCa03CUfC9eavbDYX4Qoe15iRwSq7sYzQ3GuzE/uHLvzf"
    "nqbV2DJQV5DI3wDE6gAAAAAXBkkBCV8ABwsBAAEhIQEYDF0AAA=="
)


def _cb7_bytes() -> bytes:
    return base64.b64decode(_CB7_B64)


def _pml_bytes() -> bytes:
    return (
        b"\\pTITLE=Test Book\\p\n"
        b"\\pAUTHOR=Test Author\\p\n"
        b"\n"
        b"\\xChapter 1\\x\n"
        b"\n"
        b"This is a minimal test ebook used for integration testing.\n"
    )


def _pmlz_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("book.pml", _pml_bytes())
    return buf.getvalue()


def _opf_bytes() -> bytes:
    return (
        b'<?xml version="1.0" encoding="utf-8"?>\n'
        b'<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="uid">\n'
        b'  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">\n'
        b"    <dc:title>Test Book</dc:title>\n"
        b"    <dc:creator>Test Author</dc:creator>\n"
        b'    <dc:identifier id="uid">test-opf-001</dc:identifier>\n'
        b"    <dc:language>en</dc:language>\n"
        b"  </metadata>\n"
        b"  <manifest>\n"
        b'    <item id="ch1" href="chapter1.html" media-type="text/html"/>\n'
        b"  </manifest>\n"
        b"  <spine>\n"
        b'    <itemref idref="ch1"/>\n'
        b"  </spine>\n"
        b"</package>\n"
    )


def _rtf_bytes() -> bytes:
    return (
        rb"{\rtf1\ansi\deff0"
        rb"{\fonttbl{\f0 Times New Roman;}}"
        rb"\f0\fs24 Test Book\par"
        rb"This is a minimal integration test fixture.\par"
        rb"}"
    )


def _kepub_bytes() -> bytes:
    """Minimal Kobo EPUB (EPUB with Kobo-specific metadata)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
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
            '  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"'
            '            xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata">'
            "    <dc:title>Test Book</dc:title>"
            "    <dc:creator>Test Author</dc:creator>"
            '    <dc:identifier id="uid">test-kepub-001</dc:identifier>'
            "    <dc:language>en</dc:language>"
            "  </metadata>"
            "  <manifest>"
            '    <item id="ncx"  href="toc.ncx"       media-type="application/x-dtbncx+xml"/>'
            '    <item id="ch1"  href="chapter1.xhtml" media-type="application/xhtml+xml"/>'
            "  </manifest>"
            '  <spine toc="ncx"><itemref idref="ch1"/></spine>'
            "</package>",
        )
        zf.writestr(
            "OEBPS/toc.ncx",
            '<?xml version="1.0" encoding="utf-8"?>'
            '<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">'
            '  <head><meta name="dtb:uid" content="test-kepub-001"/></head>'
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
            '<html xmlns="http://www.w3.org/1999/xhtml"'
            '      xmlns:epub="http://www.idpf.org/2007/ops">'
            "  <head><title>Chapter 1</title></head>"
            "  <body>"
            "    <h1>Chapter 1</h1>"
            "    <p>This is a minimal Kobo EPUB test fixture.</p>"
            "  </body>"
            "</html>",
        )
    return buf.getvalue()


def _cbc_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("book.cbz", _cbz_bytes())
        zf.writestr("comics.txt", "Test Collection\nbook.cbz\n")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Calibre-based conversion
# ---------------------------------------------------------------------------

_PRINT_LOCK = Lock()


def calibre_convert(src: Path, dst: Path) -> bool:
    """Convert src to dst using ebook-convert. Returns True on success."""
    result = subprocess.run(
        ["ebook-convert", str(src), str(dst)],
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0:
        with _PRINT_LOCK:
            print(f"  {yellow('WARN')}: ebook-convert {src.suffix} → {dst.suffix} failed.")
            print(red(result.stderr.decode()), end="\n\n")
        return False
    return True


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------


def download(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as exc:
        print(f"  {yellow('WARN')}: download {url} failed: {exc}")
        return False


# ---------------------------------------------------------------------------
# Main generation logic
# ---------------------------------------------------------------------------

SKIPPED = {
    "azw4",  # PDF-in-AZW wrapper; no public sample available
    "chm",  # Microsoft HTML Help binary; no public sample available
    "recipe",  # Calibre RSS feed recipe
    "downloaded_recipe",  # Calibre internal download artifact
    "pobi",  # Amazon POBI; no public sample available
    "updb",  # UPaD format; no public sample available
    "docm",  # Word macro-enabled; macro-free DOCX serves same Calibre path
}


def generate_fixures() -> None:
    FIXTURES.mkdir(exist_ok=True)
    ok: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    # ── Base EPUB ──────────────────────────────────────────────────────
    print("Copying base EPUB...")
    epub_src = FIXTURES / "book.epub"
    EPUB_TEST.copy(FIXTURES / "book.epub")
    print(f"  epub... {green('OK')}", flush=True)
    ok.append("epub")

    # ── Calibre output formats ─────────────────────────────────────────
    print(f"\nConverting EPUB → {len(output_formats) - 1} formats via Calibre...")
    for fmt in output_formats:
        if fmt == "epub":
            continue
        dst = FIXTURES / f"book.{fmt}"
        print(f"  {fmt}...", end=" ", flush=True)
        if calibre_convert(epub_src, dst):
            print(green("OK"))
            ok.append(fmt)
        else:
            failed.append(fmt)

    # ── Synthetic text/zip-based formats ──────────────────────────────
    print("\nGenerating synthetic fixtures...")
    synthetic: dict[str, tuple[str, bytes]] = {
        "txt": ("book.txt", b"Test Book\n\nThis is a minimal integration test fixture.\n"),
        "text": ("book.text", b"Test Book\n\nThis is a minimal integration test fixture.\n"),
        "html": (
            "book.html",
            b"<!DOCTYPE html><html><head><title>Test</title></head><body><h1>Test Book</h1><p>Integration test fixture.</p></body></html>",
        ),
        "htm": (
            "book.htm",
            b"<!DOCTYPE html><html><head><title>Test</title></head><body><h1>Test Book</h1><p>Integration test fixture.</p></body></html>",
        ),
        "xhtml": (
            "book.xhtml",
            b'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>Test</title></head><body><h1>Test Book</h1><p>Integration test fixture.</p></body></html>',
        ),
        "xhtm": (
            "book.xhtm",
            b'<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml"><head><title>Test</title></head><body><h1>Test Book</h1><p>Integration test fixture.</p></body></html>',
        ),
        "shtml": (
            "book.shtml",
            b"<!DOCTYPE html><html><head><title>Test</title></head><body><h1>Test Book</h1><p>Integration test fixture.</p></body></html>",
        ),
        "shtm": (
            "book.shtm",
            b"<!DOCTYPE html><html><head><title>Test</title></head><body><h1>Test Book</h1><p>Integration test fixture.</p></body></html>",
        ),
        "markdown": (
            "book.markdown",
            b"# Test Book\n\nThis is a minimal integration test fixture.\n",
        ),
        "md": ("book.md", b"# Test Book\n\nThis is a minimal integration test fixture.\n"),
        "textile": (
            "book.textile",
            b"h1. Test Book\n\nThis is a minimal integration test fixture.\n",
        ),
        "fb2": ("book.fb2", _fb2_bytes()),
        "fbz": ("book.fbz", _fbz_bytes()),
        "htmlz": ("book.htmlz", _htmlz_bytes()),
        "txtz": ("book.txtz", _txtz_bytes()),
        "cbz": ("book.cbz", _cbz_bytes()),
        "cb7": ("book.cb7", _cb7_bytes()),
        "pml": ("book.pml", _pml_bytes()),
        "pmlz": ("book.pmlz", _pmlz_bytes()),
        "opf": ("book.opf", _opf_bytes()),
        "rtf": ("book.rtf", _rtf_bytes()),
        "kepub": ("book.kepub", _kepub_bytes()),
        "cbc": ("book.cbc", _cbc_bytes()),
    }
    for fmt, (name, data) in synthetic.items():
        # Don't overwrite successful Calibre-generated files
        dst = FIXTURES / name
        if dst.exists() and fmt in ok:
            continue
        dst.write_bytes(data)
        if fmt not in ok:
            ok.append(fmt)
        print(f"  {fmt}: {green('OK')} {dim('(synthetic)')}")
        if fmt == "opf":
            # book.opf references chapter1.html by relative path; write it alongside
            (FIXTURES / "chapter1.html").write_bytes(
                b"<!DOCTYPE html><html><head><title>Chapter 1</title></head>"
                b"<body><h1>Chapter 1</h1><p>Integration test fixture.</p></body></html>"
            )

    # ── Comic archives from clach04/sample_reading_media ──────────────
    _CLACH04_URL = "https://github.com/clach04/sample_reading_media/releases/download/v0.2/sample_reading_media.zip"
    clach04_zip = Path("/tmp/sample_reading_media.zip")
    if not clach04_zip.exists():
        print("\nDownloading comic/document archive from clach04 release...")
        download(_CLACH04_URL, clach04_zip)
    if clach04_zip.exists():
        print("\nExtracting comic/document archives from clach04 release...")
        extract_map = {
            "bobby_make_believe_sample.cbr": "book.cbr",
            "bobby_make_believe_sample.cbz": None,  # already have one
            "bobby_make_believe_sample.cb7": None,  # synthetic fixture used instead
            "test_book_odt.odt": "book.odt",
        }
        with zipfile.ZipFile(clach04_zip) as zf:
            for src_name, dst_name in extract_map.items():
                if dst_name is None:
                    continue
                try:
                    data = zf.read(src_name)
                    dst = FIXTURES / dst_name
                    dst.write_bytes(data)
                    fmt = Path(dst_name).suffix.lstrip(".")
                    if fmt not in ok:
                        ok.append(fmt)
                    print(f"  {fmt}: {green('OK')} {dim('(clach04)')}")
                except KeyError:
                    print(f"  {yellow('WARN')}: {src_name} not found in clach04 zip")
    else:
        print(f"  {yellow('WARN')}: download failed, skipping cbr/odt fixtures.")
        for fmt in ("cbr", "odt"):
            failed.append(fmt)

    # ── Download DjVu from filesamples.com ────────────────────────────
    print("\nDownloading DjVu sample...")
    djvu_dst = FIXTURES / "book.djvu"
    if download("https://filesamples.com/samples/document/djvu/sample1.djvu", djvu_dst):
        ok.append("djvu")
        # djv is the same format, just alternate extension
        (FIXTURES / "book.djv").write_bytes(djvu_dst.read_bytes())
        ok.append("djv")
        print(f"  djvu: {green('OK')} {dim('(filesamples.com)')}")
        print(f"  djv: {green('OK')} {dim('(copy of djvu)')}")
    else:
        failed.append("djvu")
        failed.append("djv")

    # ── Derived formats (format aliases / near-identical formats) ──────
    print("\nCreating derived/alias format copies...")
    mobi_path = FIXTURES / "book.mobi"
    if mobi_path.exists():
        # prc is the same wire format as mobi
        (FIXTURES / "book.prc").write_bytes(mobi_path.read_bytes())
        ok.append("prc")
        print(f"  prc: {green('OK')} {dim('(copy of mobi)')}")
        # azw is essentially mobi without DRM
        (FIXTURES / "book.azw").write_bytes(mobi_path.read_bytes())
        ok.append("azw")
        print(f"  azw: {green('OK')} {dim('(copy of mobi)')}")

    # ── Skipped formats ────────────────────────────────────────────────
    for fmt in SKIPPED:
        skipped.append(fmt)

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + cyan("=" * 60))
    status = (
        red(f"DONE: {len(ok)} formats generated, {len(skipped)} skipped, {len(failed)} failed")
        if failed
        else green(
            f"DONE: {len(ok)} formats generated, {len(skipped)} skipped, {len(failed)} failed"
        )
    )
    print(status)
    print(f"\n{green(f'Generated ({len(ok)})')}: {', '.join(sorted(ok))}")
    if skipped:
        print(f"\n{yellow(f'Skipped ({len(skipped)})')}: {', '.join(sorted(skipped))}")
        print("  (no publicly available sample exists for these formats)")
    if failed:
        print(f"\n{red(f'Failed ({len(failed)})')}: {', '.join(sorted(failed))}")
        sys.exit(1)


def test_cross_format() -> None:
    """Convert every fixture against every output format in parallel and display a matrix."""
    fixtures = sorted(
        p
        for p in FIXTURES.glob("book.*")
        if p.suffix.lstrip(".") in input_formats
        and p.suffix.lstrip(".") not in (SKIPPED | _TEST_SKIP)
    )

    pairs = [(f, o) for f in fixtures for o in output_formats]
    n_workers = os.cpu_count() or 4
    print(
        f"\nCross-format: {len(fixtures)} inputs x {len(output_formats)} outputs"
        f" = {len(pairs)} pairs ({n_workers} workers)\n"
    )

    results: dict[str, dict[str, bool]] = {p.suffix.lstrip("."): {} for p in fixtures}

    def _run(fixture: Path, out_fmt: str, tmp: Path) -> tuple[str, str, bool]:
        in_fmt = fixture.suffix.lstrip(".")
        dst = tmp / f"{in_fmt}_{out_fmt}.{out_fmt}"
        return in_fmt, out_fmt, calibre_convert(fixture, dst)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with ThreadPoolExecutor(max_workers=n_workers) as executor:
            futures = {executor.submit(_run, f, o, tmp): (f, o) for f, o in pairs}
            done = 0
            for future in as_completed(futures):
                try:
                    in_fmt, out_fmt, success = future.result()
                except Exception:
                    fixture, out_fmt = futures[future]
                    in_fmt = fixture.suffix.lstrip(".")
                    success = False
                results[in_fmt][out_fmt] = success
                done += 1
                print(dim(f"  {done}/{len(pairs)}"), end="\r", flush=True)
    print()

    # ── Matrix ───────────────────────────────────────────────────────────
    col_w = max(len(f) for f in output_formats) + 1
    label_w = max(len(p.suffix.lstrip(".")) for p in fixtures) + 2

    print(f"{'Input':<{label_w}}" + "".join(f"{f:<{col_w}}" for f in output_formats))
    print("-" * (label_w + col_w * len(output_formats)))
    for fixture in fixtures:
        in_fmt = fixture.suffix.lstrip(".")
        row = f"{in_fmt:<{label_w}}"
        for out_fmt in output_formats:
            ok_cell = results[in_fmt].get(out_fmt)
            padded = f"{'o' if ok_cell else 'X':<{col_w}}"
            row += green(padded) if ok_cell else red(padded)
        print(row)

    # ── Summary ──────────────────────────────────────────────────────────
    n_ok = 0
    n_fail = 0
    all_failed = {}
    for in_fmt, row in results.items():
        for out_fmt, ok in row.items():
            if ok:
                n_ok += 1
            else:
                n_fail += 1
                all_failed.setdefault(in_fmt, []).append(out_fmt)

    print(f"\n{cyan('=' * 60)}")
    summary = (
        f"Cross-format: {green(str(n_ok))} OK, {red(str(n_fail)) if n_fail else dim('0')} failed"
    )
    print(summary)
    if n_fail > 0:
        print(f"\n{red(f'Failed ({n_fail})')}:")
        for fmt, fails in all_failed.items():
            print(f"  {fmt} ({len(fails)})  →  {', '.join(fails)}")
        sys.exit(1)


def main() -> None:
    print(cyan("~" * 60), end="\n\n")
    print(f"Supported Inputs ({len(input_formats)}):")
    print(green(bold(", ".join(sorted(input_formats)))), end="\n\n")
    print(f"Supported Outputs ({len(output_formats)}):")
    print(green(bold(", ".join(sorted(output_formats)))), end="\n\n")
    print(cyan("~" * 60), end="\n\n")

    generate_fixures()

    print("\n")
    print(cyan("~" * 60))
    print(bold("CROSS CHECK"))
    print(cyan("~" * 60), end="\n\n")

    test_cross_format()


if __name__ == "__main__":
    main()
