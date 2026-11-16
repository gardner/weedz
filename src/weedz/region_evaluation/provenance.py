"""Hash the installed package source closure, without assuming a pristine Git HEAD."""

import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path


def evaluator_provenance() -> dict:
    package = Path(__file__).resolve().parent.parent
    modules = {
        str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(package.rglob("*.py"))
        if path.is_file()
    }
    return {
        "python": platform.python_version(),
        "libraries": {name: version(name) for name in ("numpy", "Pillow", "pydantic")},
        "source_tree_sha256": hashlib.sha256(
            json.dumps(modules, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "module_sha256": modules,
    }
