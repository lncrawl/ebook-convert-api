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
    group: str | None = None
