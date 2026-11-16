"""Hash evaluator bytes actually imported, without assuming a pristine Git HEAD."""

import hashlib
import platform
from importlib.metadata import version
from pathlib import Path


def evaluator_provenance() -> dict:
    package = Path(__file__).resolve().parent.parent
    files = [*Path(__file__).resolve().parent.glob("*.py")]
    files.extend(
        package / name
        for name in (
            "contract.py",
            "contract_versions.py",
            "review_values.py",
            "manifest.py",
            "classification/batch.py",
            "classification/regions.py",
            "segmentation/ingress.py",
        )
    )
    return {
        "python": platform.python_version(),
        "libraries": {name: version(name) for name in ("numpy", "Pillow", "pydantic")},
        "module_sha256": {
            str(path.relative_to(package)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(files)
        },
    }
