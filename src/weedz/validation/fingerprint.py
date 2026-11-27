"""Cache identities that change whenever the pipeline code or its libraries change.

Checks cache raw model evidence so a full run can resume. Keying that cache by
the code that produced it means a pipeline change can't reuse stale evidence.
"""

import ast
import hashlib
import json
from collections.abc import Iterable
from importlib.metadata import version
from pathlib import Path

from PIL import Image

PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _module_path(module: str, root: Path) -> Path | None:
    relative = Path(*module.split(".")[1:])
    for candidate in (relative.with_suffix(".py"), relative / "__init__.py"):
        if (root / candidate).is_file():
            return candidate
    return None


def _imports(path: Path) -> set[str]:
    """Every weedz module a file imports, at the top level or inside a function."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return {name for name in found if name.split(".")[0] == "weedz"}


def imported_sources(*entries: Path, root: Path = PACKAGE_ROOT) -> tuple[Path, ...]:
    """The entry files plus every weedz source file they import, directly or not."""
    seen: set[Path] = set()
    pending = list(entries)
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        modules = (_module_path(name, root) for name in _imports(root / path))
        pending.extend(module for module in modules if module is not None)
    return tuple(sorted(seen))


EXIF_ORIENTATION = 0x0112


def require_stored_orientation(path: Path) -> None:
    """Refuse a photo whose EXIF rotation would put SAM3's output in a different frame.

    SAM3 reads photos EXIF-upright, while the public labels use the stored pixels.
    """
    with Image.open(path) as image:
        orientation = image.getexif().get(EXIF_ORIENTATION, 1)
    if orientation != 1:
        raise ValueError(f"{path.name} has EXIF orientation {orientation}; labels would not align")


def pipeline_fingerprint(
    sources: Iterable[Path],
    packages: Iterable[str],
    *settings: object,
    root: Path = PACKAGE_ROOT,
) -> str:
    """Hash the named source files, library versions and settings into a short key."""
    digests = [
        (path.as_posix(), hashlib.sha256((root / path).read_bytes()).hexdigest())
        for path in sources
    ]
    payload = [
        digests,
        {package: version(package) for package in packages},
        settings,
    ]
    encoded = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()[:20]
