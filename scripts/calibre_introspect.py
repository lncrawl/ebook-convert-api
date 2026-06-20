#!/usr/bin/env python

"""
Generate a Calibre conversion option catalog.

Usage:

    calibre-debug -e calibre_introspect.py ./data/catalog.json
"""

import json
import sys
import tempfile
from pathlib import Path

from calibre.constants import __version__
from calibre.customize.ui import (
    initialize_plugins,
    input_format_plugins,
    output_format_plugins,
)
from calibre.ebooks.conversion.cli import (
    add_pipeline_options,
)
from calibre.ebooks.conversion.plumber import Plumber
from calibre.utils.config import OptionParser
from calibre.utils.logging import Log

initialize_plugins()

output_path = Path(sys.argv[1])

# Calibre groups its shared pipeline options under UPPERCASE titles; map them to
# friendlier display names. Pipeline options that the parser leaves ungrouped
# (the input/output profiles) are collected under "General".
GROUP_TITLES = {
    "LOOK AND FEEL": "Look & Feel",
    "HEURISTIC PROCESSING": "Heuristic Processing",
    "SEARCH AND REPLACE": "Search & Replace",
    "STRUCTURE DETECTION": "Structure Detection",
    "TABLE OF CONTENTS": "Table of Contents",
    "METADATA": "Metadata",
    "DEBUG": "Debug",
}
UNGROUPED_TITLE = "General"


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


def collect_common_options():
    """Collect Calibre's shared pipeline options, grouped by category.

    These are the conversion knobs (margins, fonts, TOC, metadata, heuristics …)
    that apply to every conversion regardless of format. They live on the Plumber
    rather than on any single format plugin, so we drive a throwaway Plumber and
    read the option groups the CLI parser builds from it.
    """
    with tempfile.TemporaryDirectory() as tmp:
        dummy_in = Path(tmp) / "in.epub"
        dummy_in.write_text("")
        dummy_out = str(Path(tmp) / "out.epub")
        plumber = Plumber(str(dummy_in), dummy_out, Log())

        rec_by_name = {}
        for rec in plumber.pipeline_options:
            opt = getattr(rec, "option", None)
            name = getattr(opt, "name", None) if opt is not None else None
            if name:
                rec_by_name[name] = rec

        parser = OptionParser(usage="introspect")
        add_pipeline_options(parser, plumber)

    def options_for(parser_options):
        seen = set()
        results = []
        for parser_opt in parser_options:
            name = parser_opt.dest
            rec = rec_by_name.get(name) if name else None
            entry = optionrec_to_dict(rec) if rec is not None else None
            if not entry or entry["name"] in seen:
                continue
            # Use the switch the CLI parser actually registers. For boolean
            # options whose recommended value is True, Calibre exposes a negated
            # switch (e.g. dehyphenate -> --disable-dehyphenate), so the guessed
            # --<name> in optionrec_to_dict would be rejected by ebook-convert.
            entry["cli_flag"] = parser_opt.get_opt_string()
            seen.add(entry["name"])
            results.append(entry)
        results.sort(key=lambda x: x["name"])
        return results

    groups = {}

    ungrouped = options_for(parser.option_list)
    if ungrouped:
        groups[UNGROUPED_TITLE] = ungrouped

    for group in parser.option_groups:
        display = GROUP_TITLES.get(group.title)
        if display is None:  # skip DEBUG and any future unmapped group
            continue
        options = options_for(group.option_list)
        if options:
            groups[display] = options

    return groups


catalog = {
    "calibre_version": __version__,
    "common_options": {},
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


catalog["common_options"] = collect_common_options()

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

print(
    f"Common option groups: {len(catalog['common_options'])}",
    file=sys.stderr,
)

output = json.dumps(
    catalog,
    indent=2,
    ensure_ascii=False,
    sort_keys=True,
    allow_nan=True,
)
output_path.parent.mkdir(exist_ok=True, parents=True)
output_path.write_text(output)
