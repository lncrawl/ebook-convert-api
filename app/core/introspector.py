"""Parse Calibre format-pair option metadata via calibre-debug, with LRU caching."""

from __future__ import annotations

import functools
import json
import subprocess

from app.models.introspection import OptionGroup, OptionMetadata

# Python snippet executed inside calibre's bundled interpreter (calibre-debug -c).
# in_fmt and out_fmt are string-interpolated at call time — both values are
# pre-validated against INPUT_FORMATS / OUTPUT_FORMATS before this runs.
_INTROSPECT_SCRIPT = """
import json, optparse, sys
try:
    from calibre.customize.ui import plugin_for_input_format, plugin_for_output_format
    from calibre.ebooks.conversion.plumber import Plumber

    in_fmt = {in_fmt!r}
    out_fmt = {out_fmt!r}

    input_plugin = plugin_for_input_format(in_fmt)
    output_plugin = plugin_for_output_format(out_fmt)
    if input_plugin is None or output_plugin is None:
        print("[]")
        sys.exit(0)

    results = []
    seen = set()

    def add_rec(rec, group):
        name = getattr(rec, "dest", "") or ""
        if not name or name in seen:
            return
        seen.add(name)

        opt_type = "str"
        raw_type = getattr(rec, "type", None)
        choices = getattr(rec, "choices", None)
        action = getattr(rec, "action", None)

        if action in ("store_true", "store_false"):
            opt_type = "bool"
        elif raw_type == "int":
            opt_type = "int"
        elif raw_type == "float":
            opt_type = "float"
        elif choices:
            opt_type = "choice"

        option_strings = list(getattr(rec, "option_strings", []) or [])
        cli_flag = next((s for s in option_strings if s.startswith("--")), name)

        results.append(dict(
            name=name,
            cli_flag=cli_flag,
            help=(getattr(rec, "help", None) or "").replace(
                "%default", str(getattr(rec, "default", ""))
            ),
            type=opt_type,
            default=getattr(rec, "default", None),
            choices=list(choices) if choices else None,
            group=group,
        ))

    for rec in getattr(input_plugin, "options", []) or []:
        add_rec(rec, "Input ({})".format(in_fmt.upper()))
    for rec in getattr(output_plugin, "options", []) or []:
        add_rec(rec, "Output ({})".format(out_fmt.upper()))

    try:
        parser = optparse.OptionParser()
        Plumber.add_options(parser)
        for grp in parser.option_groups:
            for rec in grp.option_list:
                add_rec(rec, grp.title)
        for rec in parser.option_list:
            add_rec(rec, "General")
    except Exception:
        pass

    print(json.dumps(results))
except Exception as exc:
    import traceback
    traceback.print_exc(file=sys.stderr)
    print("[]")
"""


@functools.lru_cache(maxsize=256)
def parse_format_options(in_fmt: str, out_fmt: str) -> list[OptionGroup]:
    script = _INTROSPECT_SCRIPT.format(in_fmt=in_fmt, out_fmt=out_fmt)
    try:
        result = subprocess.run(
            ["calibre-debug", "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        data = json.loads(result.stdout.strip() or "[]")
    except Exception:
        return []

    # Preserve the insertion order from the introspect script:
    # input-plugin options → output-plugin options → Plumber groups → General
    groups: dict[str, list[OptionMetadata]] = {}
    for item in data:
        group = item.pop("group", None) or "General"
        groups.setdefault(group, []).append(OptionMetadata(**item))

    return [OptionGroup(group=g, options=opts) for g, opts in groups.items()]
