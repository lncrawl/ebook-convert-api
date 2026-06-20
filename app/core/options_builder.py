from __future__ import annotations

from typing import Any

from ..models.introspection import OptionMetadata

# These flags accept filesystem paths and could be exploited to leak or write
# files on the conversion worker. Block them regardless of what the caller sends.
_DENYLIST: frozenset[str] = frozenset(
    {
        "debug_pipeline",
        "extract_to",
        "transform_css_rules",
        "cover",
    }
)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes", "on")


def _bool_flag(opt: OptionMetadata) -> str:
    """The switch ebook-convert registers for a boolean option.

    A boolean has exactly one switch that flips its default: Calibre exposes a
    default-True option as ``--disable-<name>`` and a default-False option as
    ``--<name>``. We derive it from the default rather than trusting the
    catalog's ``cli_flag`` for booleans, which can carry the un-negated guess.
    """
    hyphenated = opt.name.replace("_", "-")
    return f"--disable-{hyphenated}" if opt.default else f"--{hyphenated}"


def build_cli_args(
    options: dict[str, Any],
    metadata: dict[str, OptionMetadata],
) -> list[str]:
    """Map a {name: value} options dict to ebook-convert CLI arguments.

    Boolean options are emitted only when the requested value differs from the
    default (the single switch flips it). Non-boolean options use the catalog's
    ``cli_flag`` and pass the value as the next argument.
    """
    args: list[str] = []
    for name, value in options.items():
        if name in _DENYLIST:
            continue
        opt = metadata.get(name)
        if opt is None:
            continue
        if opt.type == "bool":
            if _as_bool(value) != bool(opt.default):
                args.append(_bool_flag(opt))
        else:
            args.extend([opt.cli_flag, str(value)])
    return args
