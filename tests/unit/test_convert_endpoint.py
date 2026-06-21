"""Cover every branch of the POST /convert handler."""

from __future__ import annotations

import asyncio
import io
import time
import zipfile
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import app.api.convert as convert_mod
from app import state
from app.core import introspector
from app.utils.errors import ConversionError

FILES = {"file": ("book.txt", b"hello world", "text/plain")}


def test_partition_options_filters_and_drops_bad_file_values():
    metadata = introspector.options_by_name("epub", "epub")
    opts, files = convert_mod._partition_options(
        {
            "title": "Hi",  # scalar, valid → kept
            "cover": "/etc/passwd",  # file option, non-upload string → dropped
            "margin_top": None,  # unset → skipped
            "not_an_option": "x",  # not in metadata → skipped
        },
        metadata,
    )
    assert opts == {"title": "Hi"}
    assert files == {}


def _post(client, output="epub", file=FILES["file"], **data):
    return client.post("/convert", files={"file": file}, data={"output_format": output, **data})


def test_success_returns_file(client, set_convert):
    set_convert(lambda inp, outp, args: Path(outp).write_bytes(b"converted"))
    r = _post(client)
    assert r.status_code == 200, r.text
    assert r.content == b"converted"
    assert 'filename="book.epub"' in r.headers["content-disposition"]


def test_only_set_options_are_passed(client, set_convert):
    captured = {}
    set_convert(lambda inp, outp, args: (captured.update(args=args), Path(outp).write_bytes(b"x")))
    r = _post(client, output="epub", margin_top="36")
    assert r.status_code == 200
    assert "--margin-top" in captured["args"]
    assert "36.0" in captured["args"]


def test_unsupported_input_extension(client):
    r = _post(client, file=("book.xyz", b"x", "application/octet-stream"))
    assert r.status_code == 400
    assert "supported input format" in r.json()["detail"]


def test_no_extension(client):
    r = _post(client, file=("book", b"x", "application/octet-stream"))
    assert r.status_code == 400


def test_busy_returns_503(client):
    # Replace the semaphore with an exhausted one so the fast-path busy check trips.
    state.set_semaphore(asyncio.Semaphore(0))
    r = _post(client)
    assert r.status_code == 503
    assert r.headers["Retry-After"] == "5"


def test_upload_too_large(client, monkeypatch, set_convert):
    set_convert(lambda inp, outp, args: Path(outp).write_bytes(b"x"))
    monkeypatch.setattr(convert_mod, "_MAX_UPLOAD_BYTES", 4)
    r = _post(client, file=("book.txt", b"way too many bytes", "text/plain"))
    assert r.status_code == 413


def test_conversion_error_returns_400(client, set_convert):
    def boom(inp, outp, args):
        raise ConversionError("calibre exploded")

    set_convert(boom)
    r = _post(client)
    assert r.status_code == 400
    assert "calibre exploded" in r.json()["detail"]


def test_timeout_returns_504(client, monkeypatch, set_convert):
    monkeypatch.setattr(convert_mod.settings, "conversion_timeout_seconds", 0.01)

    def slow(inp, outp, args):
        time.sleep(0.5)
        Path(outp).write_bytes(b"x")

    set_convert(slow)
    r = _post(client)
    assert r.status_code == 504


def test_broken_pool_resets_and_returns_503(client, monkeypatch, set_convert):
    reset_calls = []
    original_reset = state.reset_executor

    def tracking_reset(broken=None):
        reset_calls.append(broken)
        original_reset(broken=None)

    monkeypatch.setattr(state, "reset_executor", tracking_reset)

    def crash(inp, outp, args):
        raise BrokenProcessPool("worker died")

    set_convert(crash)
    r = _post(client)
    assert r.status_code == 503
    assert reset_calls  # reset_executor was invoked


def test_directory_output_is_zipped(client, set_convert):
    def make_dir(inp, outp, args):
        d = Path(outp)
        d.mkdir()
        (d / "index.html").write_text("<html></html>")
        (d / "sub").mkdir()
        (d / "sub" / "a.css").write_text("body{}")

    set_convert(make_dir)
    r = _post(client, output="oeb")
    assert r.status_code == 200
    assert zipfile.is_zipfile(io.BytesIO(r.content))


def test_missing_output_returns_500(client, set_convert):
    set_convert(lambda inp, outp, args: None)  # writes nothing
    r = _post(client)
    assert r.status_code == 500
    assert "no output file" in r.json()["detail"]


def test_unknown_output_format_rejected(client):
    r = _post(client, output="not_a_format")
    assert r.status_code == 422  # constrained by the enum annotation


def test_file_option_upload_is_saved_and_passed(client, set_convert):
    captured = {}

    def fake(inp, outp, args):
        idx = args.index("--cover")
        path = args[idx + 1]
        captured["path"] = path
        captured["bytes"] = Path(path).read_bytes()
        Path(outp).write_bytes(b"x")

    set_convert(fake)
    r = client.post(
        "/convert",
        files={
            "file": ("book.txt", b"hello", "text/plain"),
            "cover": ("art.jpg", b"\xff\xd8imagedata", "image/jpeg"),
        },
        data={"output_format": "epub"},
    )
    assert r.status_code == 200, r.text
    # The flag points at a file saved in the job temp dir, keeping the suffix,
    # and holds exactly the uploaded bytes — not a caller-supplied server path.
    assert captured["path"].endswith(".jpg")
    assert captured["bytes"] == b"\xff\xd8imagedata"


def test_file_option_as_plain_string_is_rejected(client, set_convert):
    set_convert(lambda inp, outp, args: Path(outp).write_bytes(b"x"))
    # A file-path option may not be smuggled in as a free-text server path.
    r = _post(client, output="epub", cover="/etc/passwd")
    assert r.status_code == 422


def test_empty_file_option_upload_is_ignored(client, set_convert):
    captured = {}
    set_convert(lambda inp, outp, args: (captured.update(args=args), Path(outp).write_bytes(b"x")))
    # An empty cover part (no filename) is treated as unset, not passed through.
    r = client.post(
        "/convert",
        files={
            "file": ("book.txt", b"hi", "text/plain"),
            "cover": ("", b"", "application/octet-stream"),
        },
        data={"output_format": "epub"},
    )
    assert r.status_code == 200, r.text
    assert "--cover" not in captured["args"]


def test_unexpected_error_returns_500(client, set_convert, monkeypatch):
    set_convert(lambda inp, outp, args: Path(outp).write_bytes(b"converted"))

    # A non-HTTPException raised after a successful conversion (here, building the
    # response) is wrapped as a 500 and the temp dir is still cleaned up.
    def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(convert_mod, "FileResponse", boom)
    r = _post(client)
    assert r.status_code == 500
    assert "kaboom" in r.json()["detail"]
