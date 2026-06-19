"""Load the pre-generated Calibre option catalog from disk and shape it for the API."""

from __future__ import annotations

import functools
from pathlib import Path

from app.models.introspection import OptionCatalog, OptionGroup

# data/catalog.json lives at project root (/app/data/catalog.json in container)
CATALOG_PATH = Path(__file__).parent.parent.parent / "data" / "catalog.json"

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


def input_formats() -> list[str]:
    return sorted(get_catalog().input_plugins)


def output_formats() -> list[str]:
    return sorted(get_catalog().output_plugins)


def _ordered_common_groups(common: dict[str, list]) -> list[str]:
    known = [g for g in _COMMON_ORDER if g in common]
    extra = [g for g in common if g not in _COMMON_ORDER]
    return known + extra


def combined_options(in_fmt: str, out_fmt: str) -> list[OptionGroup]:
    """Every option valid for an in_fmt -> out_fmt conversion, grouped for display.

    Order: the input-format options, then each shared category, then the
    output-format options. Empty groups are omitted.
    """
    catalog = get_catalog()
    groups: list[OptionGroup] = []

    input_opts = catalog.input_plugins.get(in_fmt, [])
    if input_opts:
        groups.append(OptionGroup(group="Input", options=input_opts))

    for name in _ordered_common_groups(catalog.common_options):
        options = catalog.common_options[name]
        if options:
            groups.append(OptionGroup(group=name, options=options))

    output_opts = catalog.output_plugins.get(out_fmt, [])
    if output_opts:
        groups.append(OptionGroup(group="Output", options=output_opts))

    return groups
