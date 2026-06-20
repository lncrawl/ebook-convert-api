"""Serve the bundled single-page conversion UI (Jinja-rendered, assets inlined)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from app.core import introspector

router = APIRouter()

_STATIC_DIR = Path(__file__).parent.parent / "static"
_templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _read_asset(name: str) -> str:
    """Read a CSS/JS source file to inline into the page.

    Neutralize any closing-tag token so the content can't break out of its
    inline <style>/<script> wrapper (our assets contain none, but stay safe).
    """
    text = (_STATIC_DIR / name).read_text()
    return text.replace("</style", "<\\/style").replace("</script", "<\\/script")


@router.get("/", include_in_schema=False)
async def index(request: Request):
    # Inject the format lists so the page needs no client fetch("/formats").
    # Escape "<" so the JSON can't break out of the <script> data island.
    bootstrap = json.dumps(
        {
            "input_formats": introspector.input_formats(),
            "output_formats": introspector.output_formats(),
        }
    ).replace("<", "\\u003c")

    # no-store: never let the browser cache the HTML entry point, so a redeploy
    # can't be masked by a previously cached page. CSS/JS are inlined below, so
    # the whole UI is one self-contained, always-fresh document.
    return _templates.TemplateResponse(
        request,
        "index.html",
        {
            "bootstrap": bootstrap,
            "css": _read_asset("styles.css"),
            "js": _read_asset("app.js"),
        },
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
    )
