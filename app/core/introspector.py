"""Load the pre-generated Calibre option catalog from disk and shape it for the API."""

from __future__ import annotations

import functools
from pathlib import Path

from ..models.introspection import OptionCatalog, OptionGroup, OptionMetadata
from .options_builder import _HIDDEN_OPTIONS, FILE_OPTIONS

# data/catalog.json lives at project root (/app/data/catalog.json in container)
REPO_ROOT = Path(__file__).parents[2]
CATALOG_PATH = REPO_ROOT / "data" / "catalog.json"

# Preferred display order for the common-option categories. Any group present in
# the catalog but missing here is appended afterwards in catalog order.
_COMMON_ORDER = (
    "Look & Feel",
    "Structure Detection",
    "Table of Contents",
    "Heuristic Processing",
    "Search & Replace",
    "Metadata",
    "General",
    "Debug",
)


@functools.lru_cache(maxsize=1)
def get_catalog() -> OptionCatalog:
    return OptionCatalog.model_validate_json(CATALOG_PATH.read_text())


def calibre_version() -> str:
    return get_catalog().calibre_version


def input_formats() -> list[str]:
    return sorted(get_catalog().input_plugins)


def output_formats() -> list[str]:
    return sorted(get_catalog().output_plugins)


def _ordered_common_groups(common: dict[str, list]) -> list[str]:
    known = [g for g in _COMMON_ORDER if g in common]
    extra = [g for g in common if g not in _COMMON_ORDER]
    return known + extra


def _visible(options: list[OptionMetadata]) -> list[OptionMetadata]:
    """Drop options that are never surfaced to API users (unsafe/debug flags)."""
    return [opt for opt in options if opt.name not in _HIDDEN_OPTIONS]


def _mark_file_options(options: list[OptionMetadata]) -> list[OptionMetadata]:
    """Re-type the catalog's file-path options as ``"file"`` for display/dispatch.

    Calibre advertises these as plain ``str`` flags, but the API takes an upload
    for them. The ``"file"`` type tells the UI to render a file picker and the
    endpoint to substitute the saved upload path. Copies are returned so the
    cached catalog objects stay untouched.
    """
    return [
        opt.model_copy(update={"type": "file"}) if opt.name in FILE_OPTIONS else opt
        for opt in options
    ]


def combined_options(in_fmt: str, out_fmt: str) -> list[OptionGroup]:
    """Every option valid for an in_fmt -> out_fmt conversion, grouped for display.

    Order: the input-format options, then each shared category, then the
    output-format options. Empty groups are omitted.
    """
    catalog = get_catalog()
    groups: list[OptionGroup] = []

    input_opts = _visible(catalog.input_plugins.get(in_fmt, []))
    if input_opts:
        groups.append(OptionGroup(group="Input", options=_mark_file_options(input_opts)))

    for name in _ordered_common_groups(catalog.common_options):
        options = _visible(catalog.common_options[name])
        if options:
            groups.append(OptionGroup(group=name, options=_mark_file_options(options)))

    output_opts = _visible(catalog.output_plugins.get(out_fmt, []))
    if output_opts:
        groups.append(OptionGroup(group="Output", options=_mark_file_options(output_opts)))

    return groups


def options_by_name(in_fmt: str, out_fmt: str) -> dict[str, OptionMetadata]:
    """Map option name -> metadata for an in_fmt -> out_fmt conversion."""
    return {opt.name: opt for group in combined_options(in_fmt, out_fmt) for opt in group.options}
