from pydantic import BaseModel


class FormatList(BaseModel):
    input_formats: list[str]
    output_formats: list[str]


class OptionMetadata(BaseModel):
    name: str
    cli_flag: str
    help: str
    type: str  # "str" | "int" | "float" | "bool" | "choice"
    default: str | int | float | bool | None = None
    choices: list[str] | None = None


class OptionGroup(BaseModel):
    group: str
    options: list[OptionMetadata]


class OptionCatalog(BaseModel):
    """The full Calibre option catalog, loaded from data/catalog.json.

    `input_plugins` / `output_plugins` map a format to its format-specific
    options. `common_options` maps a display category (e.g. "Look & Feel") to
    the shared pipeline options that apply to every conversion.
    """

    calibre_version: str
    input_plugins: dict[str, list[OptionMetadata]]
    output_plugins: dict[str, list[OptionMetadata]]
    common_options: dict[str, list[OptionMetadata]]
