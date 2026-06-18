import shutil
import tempfile
from pathlib import Path


class ConversionTempDir:
    """Sync context manager — create a temp dir, guarantee cleanup on exit."""

    def __init__(self) -> None:
        self.path: Path | None = None

    def __enter__(self) -> Path:
        self.path = Path(tempfile.mkdtemp(prefix="ebook-convert-"))
        return self.path

    def __exit__(self, *_: object) -> None:
        if self.path and self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)

    def cleanup(self) -> None:
        self.__exit__()
