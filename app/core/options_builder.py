from __future__ import annotations

from types import SimpleNamespace

from app.models.options_universal import ConversionOptions

# These flags accept filesystem paths and could be exploited to leak or write
# files on the conversion worker. Block them regardless of what the caller sends.
_DENYLIST: frozenset[str] = frozenset({
    "debug_pipeline",
    "extract_to",
    "transform_css_rules",
    "cover",
})


def build_plumber_options(options: ConversionOptions) -> SimpleNamespace:
    """Convert a ConversionOptions model into a SimpleNamespace for Plumber.merge_ui_recommendations."""
    ns: dict[str, object] = {}

    for key, value in options.model_dump(exclude_none=True).items():
        if key == "extra_options":
            continue
        if key in _DENYLIST:
            continue
        ns[key] = value

    for raw_key, value in (options.extra_options or {}).items():
        # Normalise: strip leading --, replace hyphens with underscores
        key = raw_key.lstrip("-").replace("-", "_")
        if key in _DENYLIST:
            continue
        # Boolean flags passed with null value become True
        ns[key] = True if value is None else value

    return SimpleNamespace(**ns)
