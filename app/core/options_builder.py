from __future__ import annotations

from types import SimpleNamespace
from typing import Any

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


def build_plumber_options(options: dict[str, Any]) -> SimpleNamespace:
    """Map a {name: value} options dict to a SimpleNamespace for Plumber.

    Keys match the option names returned by GET /formats/{in}/{out}/options.
    A null/None value means a boolean flag (passed with no argument to the CLI).
    Keys not present in the dict are not set (Calibre uses its own defaults).
    """
    ns: dict[str, object] = {}
    for raw_key, raw_value in options.items():
        key = raw_key.lstrip("-").replace("-", "_")
        if key in _DENYLIST:
            continue
        ns[key] = True if raw_value is None else raw_value
    return SimpleNamespace(**ns)
