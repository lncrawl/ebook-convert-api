"""Cover the metadata, health, UI, and auth-middleware paths."""

from __future__ import annotations

from fastapi.testclient import TestClient

import app.main as main_mod

# --- health ----------------------------------------------------------------


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "calibre_version" in body
    assert "max_concurrent_jobs" in body


def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"status": "ready"}


# --- formats ---------------------------------------------------------------


def test_list_formats(client):
    r = client.get("/formats")
    assert r.status_code == 200
    body = r.json()
    assert body["input_formats"] and body["output_formats"]


def test_format_options_success(client):
    r = client.get("/formats/epub/pdf/options")
    assert r.status_code == 200
    groups = r.json()
    assert isinstance(groups, list) and groups


def test_format_options_unknown_input(client):
    r = client.get("/formats/nope/pdf/options")
    assert r.status_code == 404
    assert "input format" in r.json()["detail"]


def test_format_options_unknown_output(client):
    r = client.get("/formats/epub/nope/options")
    assert r.status_code == 404
    assert "output format" in r.json()["detail"]


# --- UI --------------------------------------------------------------------


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "ebook-convert" in r.text
    # HTML entry point is never cached so a redeploy is always visible.
    assert r.headers["cache-control"].startswith("no-store")


# --- auth middleware -------------------------------------------------------


def test_auth_middleware_passthrough(monkeypatch):
    # USE_AUTH=true wires in the stub middleware, which currently passes through.
    monkeypatch.setattr(main_mod.settings, "use_auth", True)
    with TestClient(main_mod.create_app()) as c:
        r = c.get("/ready")
        assert r.status_code == 200
        assert r.json() == {"status": "ready"}
