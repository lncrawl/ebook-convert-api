"""Parse Calibre format-pair option metadata, with LRU caching per (in_fmt, out_fmt) pair."""

from __future__ import annotations

import functools

from app.models.introspection import OptionMetadata


@functools.lru_cache(maxsize=256)
def parse_format_options(in_fmt: str, out_fmt: str) -> list[OptionMetadata]:
    """Return option metadata for a given input/output format pair.

    Calibre's option system is built around optparse.OptionParser. We instantiate
    the input and output plugins to gather their option definitions.
    """
    try:
        from calibre.customize.ui import plugin_for_input_format, plugin_for_output_format
        from calibre.ebooks.conversion.plumber import Plumber
    except ImportError:
        return []

    input_plugin = plugin_for_input_format(in_fmt)
    output_plugin = plugin_for_output_format(out_fmt)
    if input_plugin is None or output_plugin is None:
        return []

    results: list[OptionMetadata] = []
    seen: set[str] = set()

    def _add_from_rec(rec: object, group: str | None) -> None:
        name: str = getattr(rec, "dest", "") or ""
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

        option_strings: list[str] = list(getattr(rec, "option_strings", []) or [])
        cli_flag = next((s for s in option_strings if s.startswith("--")), name)

        results.append(
            OptionMetadata(
                name=name,
                cli_flag=cli_flag,
                help=(getattr(rec, "help", None) or "").replace(
                    "%default", str(getattr(rec, "default", ""))
                ),
                type=opt_type,
                default=getattr(rec, "default", None),
                choices=list(choices) if choices else None,
                group=group,
            )
        )

    def _collect_plugin_options(plugin: object, group_label: str) -> None:
        for rec in getattr(plugin, "options", []) or []:
            _add_from_rec(rec, group_label)

    _collect_plugin_options(input_plugin, f"Input ({in_fmt.upper()})")
    _collect_plugin_options(output_plugin, f"Output ({out_fmt.upper()})")

    # Also collect universal options via a dummy Plumber option parser
    try:
        import optparse

        parser = optparse.OptionParser()
        Plumber.add_options(parser)  # type: ignore[attr-defined]
        for group in parser.option_groups:
            for rec in group.option_list:
                _add_from_rec(rec, group.title)
        for rec in parser.option_list:
            _add_from_rec(rec, "General")
    except Exception:
        pass

    return results
