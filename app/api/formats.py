from fastapi import APIRouter, HTTPException

from ..core import introspector
from ..models.introspection import FormatList, OptionGroup

router = APIRouter(prefix="/formats")


@router.get("", response_model=FormatList)
async def list_formats() -> FormatList:
    return FormatList(
        input_formats=introspector.input_formats(),
        output_formats=introspector.output_formats(),
    )


@router.get("/{in_fmt}/{out_fmt}/options", response_model=list[OptionGroup])
async def format_options(in_fmt: str, out_fmt: str) -> list[OptionGroup]:
    in_fmt = in_fmt.lower()
    out_fmt = out_fmt.lower()

    if in_fmt not in introspector.input_formats():
        raise HTTPException(status_code=404, detail=f"Unsupported input format: {in_fmt!r}")
    if out_fmt not in introspector.output_formats():
        raise HTTPException(status_code=404, detail=f"Unsupported output format: {out_fmt!r}")

    return introspector.combined_options(in_fmt, out_fmt)
