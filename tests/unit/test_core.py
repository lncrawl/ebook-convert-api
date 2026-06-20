"""Cover the core helpers: options_builder, options_schema, introspector,
converter, tempfiles."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import introspector, options_schema
from app.core.converter import convert
from app.core.options_builder import _as_bool, _bool_flag, build_cli_args
from app.models.introspection import OptionMetadata
from app.utils.errors import ConversionError
from app.utils.tempfiles import ConversionTempDir


def _meta(name, type_, default=None, cli_flag=None, choices=None):
    return OptionMetadata(
        name=name,
        cli_flag=cli_flag or f"--{name.replace('_', '-')}",
        help="",
        type=type_,
        default=default,
        choices=choices,
    )


# --- options_builder -------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        ("true", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        (False, False),
        ("no", False),
    ],
)
def test_as_bool(value, expected):
    assert _as_bool(value) is expected


def test_bool_flag_polarity():
    assert _bool_flag(_meta("dehyphenate", "bool", default=True)) == "--disable-dehyphenate"
    assert _bool_flag(_meta("enable_heuristics", "bool", default=False)) == "--enable-heuristics"


def test_build_cli_args_scalar_and_bool():
    meta = {
        "margin_top": _meta("margin_top", "int", default=5),
        "dehyphenate": _meta("dehyphenate", "bool", default=True),
        "enable_heuristics": _meta("enable_heuristics", "bool", default=False),
    }
    args = build_cli_args(
        {"margin_top": 36, "dehyphenate": "false", "enable_heuristics": "true"}, meta
    )
    assert args == ["--margin-top", "36", "--disable-dehyphenate", "--enable-heuristics"]


def test_build_cli_args_skips_bool_equal_to_default():
    meta = {"dehyphenate": _meta("dehyphenate", "bool", default=True)}
    assert build_cli_args({"dehyphenate": "true"}, meta) == []


def test_build_cli_args_skips_denylisted_and_unknown():
    meta = {"margin_top": _meta("margin_top", "int", default=5)}
    # "cover" is denylisted; "mystery" has no metadata → both dropped.
    assert build_cli_args({"cover": "/etc/passwd", "mystery": "x"}, meta) == []


# --- options_schema --------------------------------------------------------


def test_describe_variants():
    assert options_schema._describe(_meta("a", "str", default="x")) == " (default: x)".strip()
    helped = options_schema._describe(
        OptionMetadata(name="a", cli_flag="--a", help="Do a thing", type="str", default="x")
    )
    assert helped == "Do a thing (default: x)"
    no_default = OptionMetadata(
        name="a", cli_flag="--a", help="Just help", type="str", default=None
    )
    assert options_schema._describe(no_default) == "Just help"
    empty = OptionMetadata(name="a", cli_flag="--a", help="", type="str", default=None)
    assert options_schema._describe(empty) == ""


def test_annotation_for_choice_and_fallback():
    choice = options_schema._annotation_for(_meta("c", "choice", choices=["a", "b"]))
    assert choice is not None
    weird = options_schema._annotation_for(_meta("c", "weird-type"))
    assert weird is not None  # falls back to str | None


def test_convert_signature_has_fixed_params():
    params = options_schema.convert_signature().parameters
    assert {"background_tasks", "file", "output_format"} <= set(params)


# --- introspector ----------------------------------------------------------


def test_introspector_format_lists_and_version():
    assert introspector.input_formats()
    assert introspector.output_formats()
    assert isinstance(introspector.calibre_version(), str)


def test_combined_and_by_name_for_known_pair():
    in_fmt = introspector.input_formats()[0]
    out_fmt = introspector.output_formats()[0]
    groups = introspector.combined_options(in_fmt, out_fmt)
    assert groups
    by_name = introspector.options_by_name(in_fmt, out_fmt)
    assert by_name and all(isinstance(v, OptionMetadata) for v in by_name.values())


def test_combined_options_unknown_pair_is_empty_of_format_groups():
    groups = introspector.combined_options("nope_in", "nope_out")
    names = {g.group for g in groups}
    assert "Input" not in names and "Output" not in names


def test_ordered_common_groups_appends_unknown():
    order = introspector._ordered_common_groups({"Metadata": [1], "Custom Extra": [1]})
    assert order[-1] == "Custom Extra"


# --- converter -------------------------------------------------------------


def test_converter_success(monkeypatch):
    monkeypatch.setattr(
        "app.core.converter.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )
    convert("in.epub", "out.pdf", ["--x"])  # should not raise


def test_converter_nonzero_raises(monkeypatch):
    monkeypatch.setattr(
        "app.core.converter.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="bad input"),
    )
    with pytest.raises(ConversionError, match="bad input"):
        convert("in.epub", "out.pdf", [])


def test_converter_missing_binary_raises(monkeypatch):
    def raise_fnf(*a, **k):
        raise FileNotFoundError

    monkeypatch.setattr("app.core.converter.subprocess.run", raise_fnf)
    with pytest.raises(ConversionError, match="not found"):
        convert("in.epub", "out.pdf", [])


# --- tempfiles -------------------------------------------------------------


def test_conversion_tempdir_lifecycle():
    tmp = ConversionTempDir()
    with tmp as path:
        assert path.exists()
        (path / "f.txt").write_text("x")
    assert not path.exists()


def test_conversion_tempdir_cleanup_method():
    tmp = ConversionTempDir()
    path = tmp.__enter__()
    assert path.exists()
    tmp.cleanup()
    assert not path.exists()
