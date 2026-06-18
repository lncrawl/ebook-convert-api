from fastapi import HTTPException


class ConversionError(RuntimeError):
    pass


def http_error(status: int, detail: str, **extra: object) -> HTTPException:
    return HTTPException(status_code=status, detail={"detail": detail, **extra})
