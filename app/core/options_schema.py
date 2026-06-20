"""Build the POST /convert endpoint signature from the Calibre option catalog.

Every catalog option becomes an individual, typed keyword-only parameter so that
FastAPI renders it as a flattened multipart form field in the OpenAPI/Swagger docs
(number/boolean inputs, enum dropdowns for `choice` options, per-option help text).
"""

from __future__ import annotations

import inspect
import re
from typing import Annotated, Any, Literal

from fastapi import BackgroundTasks, Form, UploadFile

from app.core import introspector
from app.core.options_builder import _DENYLIST
from app.models.introspection import OptionMetadata

# Map a catalog `type` string to the Python annotation used for its form field.
_SCALAR_TYPES: dict[str, type] = {
    "bool": bool,
    "int": int,
    "float": float,
    "str": str,
}

# Required output_format rendered as an enum dropdown in Swagger.
OutputFormat = Literal[tuple(introspector.output_formats())]  # type: ignore[valid-type]

# Fixed endpoint parameters — a catalog option sharing one of these names (e.g.
# `output_format`) is skipped to avoid a duplicate parameter in the signature.
_RESERVED = frozenset({"background_tasks", "file", "output_format"})


def _annotation_for(opt: OptionMetadata) -> object:
    inner: Any
    if opt.type == "choice" and opt.choices:
        inner = Literal[tuple(opt.choices)]
    else:
        inner = _SCALAR_TYPES.get(opt.type, str)
    return inner | None


def _describe(opt: OptionMetadata) -> str:
    help_text = opt.help or ""
    help_text = re.sub(r"\<[\w\d]+\> or \<[\d\w]+\>", "or", help_text)
    if opt.default not in (None, ""):
        suffix = f" (default: {opt.default})"
        return f"{help_text}{suffix}" if help_text else suffix.strip()
    return help_text


def _option_parameters() -> list[inspect.Parameter]:
    """One keyword-only Form parameter per unique catalog option (denylist excluded)."""
    catalog = introspector.get_catalog()
    seen: set[str] = set(_RESERVED)
    params: list[inspect.Parameter] = []
    for group in (
        *catalog.common_options.values(),
        *catalog.input_plugins.values(),
        *catalog.output_plugins.values(),
    ):
        for opt in group:
            if opt.name in _DENYLIST or opt.name in seen:
                continue
            seen.add(opt.name)
            params.append(
                inspect.Parameter(
                    opt.name,
                    inspect.Parameter.KEYWORD_ONLY,
                    default=None,
                    annotation=Annotated[_annotation_for(opt), Form(description=_describe(opt))],
                )
            )
    return params


def convert_signature() -> inspect.Signature:
    """Signature for the /convert endpoint: file + output_format + every option field.

    The leading parameters mirror the real function so FastAPI's introspection and the
    actual call agree; the option fields are collected by the function's ``**options``.
    """
    fixed = [
        inspect.Parameter(
            "background_tasks", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=BackgroundTasks
        ),
        inspect.Parameter("file", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=UploadFile),
        inspect.Parameter(
            "output_format",
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Annotated[OutputFormat, Form(description="Target output format")],
        ),
    ]
    return inspect.Signature([*fixed, *_option_parameters()])


def valid_option_names(in_fmt: str, out_fmt: str) -> set[str]:
    """Option names Calibre accepts for an in_fmt -> out_fmt conversion."""
    return {
        opt.name
        for group in introspector.combined_options(in_fmt, out_fmt)
        for opt in group.options
    }
