"""
Patch Calibre source to remove Qt/PyQt6 dependencies before building.
Run from the Calibre source root: python3 docker/patch_calibre.py

Three patches:
  1. pyproject.toml      — strip PyQt6* and PyQt_builder dependency lines
  2. setup/extensions.json — mark sip_files extensions as optional
  3. setup/build_environment.py — make QMAKE discovery non-fatal
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(".")


def patch_pyproject():
    path = ROOT / "pyproject.toml"
    if not path.exists():
        print("SKIP pyproject.toml — not found", file=sys.stderr)
        return
    original = path.read_text()
    lines = original.splitlines(keepends=True)
    skip_patterns = re.compile(r"PyQt6_sip|PyQt6|PyQt6_WebEngine|PyQt_builder")
    filtered = [l for l in lines if not skip_patterns.search(l)]
    removed = len(lines) - len(filtered)
    path.write_text("".join(filtered))
    print(f"patch 1/3 pyproject.toml: removed {removed} lines")


def patch_extensions_json():
    path = ROOT / "setup" / "extensions.json"
    if not path.exists():
        print("SKIP extensions.json — not found", file=sys.stderr)
        return
    data = json.loads(path.read_text())
    patched = 0
    for ext in data:
        if ext.get("sip_files"):
            ext["optional"] = True
            patched += 1
    path.write_text(json.dumps(data, indent=2))
    print(f"patch 2/3 extensions.json: marked {patched} sip_files extensions optional")


def patch_build_environment():
    path = ROOT / "setup" / "build_environment.py"
    if not path.exists():
        print("SKIP build_environment.py — not found", file=sys.stderr)
        return
    src = path.read_text()

    # Replace hard QMAKE assignment with which-based discovery
    src = re.sub(
        r"^QMAKE\s*=\s*['\"]qmake['\"]",
        "import shutil as _shutil\nQMAKE = _shutil.which('qmake6') or _shutil.which('qmake') or None",
        src,
        flags=re.MULTILINE,
    )

    # Guard readvar() to return '' when QMAKE is None (avoids subprocess.CalledProcessError)
    src = re.sub(
        r"(def readvar\(.*?\):)",
        r"\1\n    if not QMAKE: return ''",
        src,
    )

    # Guard the qt dict assignment so it's skipped when QMAKE is absent
    src = re.sub(
        r"^(qt\s*=\s*\{)",
        "qt = {'libs': '', 'plugins': '', 'libdir': '', 'version_str': '0.0.0', 'inc': ''} if not QMAKE else \\1",
        src,
        count=1,
        flags=re.MULTILINE,
    )

    path.write_text(src)
    print("patch 3/3 build_environment.py: QMAKE made non-fatal")


if __name__ == "__main__":
    patch_pyproject()
    patch_extensions_json()
    patch_build_environment()
    print("all patches applied")
