from fastapi import APIRouter

from app.core.formats import INPUT_FORMATS, OUTPUT_FORMATS, InputFormat, OutputFormat
from app.core.introspector import parse_format_options
from app.models.introspection import FormatList, OptionGroup

router = APIRouter(prefix="/formats")


@router.get("", response_model=FormatList)
async def list_formats() -> FormatList:
    return FormatList(
        input_formats=sorted(INPUT_FORMATS),
        output_formats=sorted(OUTPUT_FORMATS),
    )


@router.get("/{in_fmt}/{out_fmt}/options", response_model=list[OptionGroup])
async def format_options(in_fmt: InputFormat, out_fmt: OutputFormat) -> list[OptionGroup]:
    return parse_format_options(in_fmt, out_fmt)
