#!/usr/bin/env python

"""
Generate a Calibre conversion option catalog.

Usage:

    calibre-debug -e calibre_introspect.py output.json
"""

import json
import sys
from pathlib import Path

from calibre.customize.ui import (  # pyright: ignore[reportMissingImports]
    initialize_plugins,
    input_format_plugins,
    output_format_plugins,
)

initialize_plugins()

output_path = Path(sys.argv[1])


def optionrec_to_dict(rec):
    opt = getattr(rec, "option", None)
    if opt is None:
        return None

    name = getattr(opt, "name", None)
    if not name:
        return None

    choices = getattr(opt, "choices", None)
    default = getattr(rec, "recommended_value", None)

    if isinstance(default, bool):
        typ = "bool"
    elif isinstance(default, int):
        typ = "int"
    elif isinstance(default, float):
        typ = "float"
    elif choices:
        typ = "choice"
    else:
        typ = "str"

    help_text = getattr(opt, "help", None) or getattr(opt, "long_switch", None) or ""

    return {
        "name": name,
        "cli_flag": f"--{name.replace('_', '-')}",
        "help": help_text,
        "type": typ,
        "default": default,
        "choices": list(choices) if choices else None,
    }


def collect_options(plugin):
    seen = set()
    results = []

    for attr in ("common_options", "options"):
        for rec in getattr(plugin, attr, set()) or set():
            entry = optionrec_to_dict(rec)

            if not entry:
                continue

            if entry["name"] in seen:
                continue

            seen.add(entry["name"])
            results.append(entry)

    results.sort(key=lambda x: x["name"])
    return results


catalog = {
    "input_plugins": {},
    "output_plugins": {},
}

for plugin in input_format_plugins():
    formats = sorted(fmt.lower() for fmt in getattr(plugin, "file_types", []))

    options = collect_options(plugin)

    for fmt in formats:
        catalog["input_plugins"][fmt] = options


for plugin in output_format_plugins():
    formats = [plugin.file_type.lower()]

    options = collect_options(plugin)

    for fmt in formats:
        catalog["output_plugins"][fmt] = options


catalog["input_plugins"] = dict(sorted(catalog["input_plugins"].items()))

catalog["output_plugins"] = dict(sorted(catalog["output_plugins"].items()))

print(
    f"Input formats: {len(catalog['input_plugins'])}",
    file=sys.stderr,
)

print(
    f"Output formats: {len(catalog['output_plugins'])}",
    file=sys.stderr,
)

output = json.dumps(
    catalog,
    indent=2,
    ensure_ascii=False,
    sort_keys=True,
    allow_nan=True,
)
output_path.parent.mkdir(exist_ok=True)
output_path.write_text(output)
