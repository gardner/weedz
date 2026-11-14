"""Small stand-ins for a model bundle: fake artefacts, a parity record and a signing key.

Nothing here downloads or runs a model; the "image tower" is a few random bytes.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from weedz.bundles.manifest import BundleSpec
from weedz.bundles.text_table import prompts
from weedz.discovery.inference import MODELS
from weedz.discovery.parity import THRESHOLDS

VARIANT = "onnx-fp16"
DIMENSIONS = 4


def write_artefacts(folder: Path) -> tuple[Path, Path]:
    """An image tower (random bytes) and a text table with one row per fixed prompt."""
    folder.mkdir(parents=True, exist_ok=True)
    tower = folder / "visual-fp16.onnx"
    tower.write_bytes(b"not really an onnx graph " * 64)
    table = folder / "text.f32"
    table.write_bytes(bytes(4 * DIMENSIONS * len(prompts())))
    return tower, table


def parity_benchmark(folder: Path, tower: Path, passed: bool = True, **override: Any) -> Path:
    """A parity benchmark whose one variant measured exactly `tower`'s bytes."""
    model = MODELS["bioclip-2"]
    variant = {
        "model": model["repo"],
        "revision": model["revision"],
        "artefact_sha256": hashlib.sha256(tower.read_bytes()).hexdigest(),
        "parity": {"thresholds": THRESHOLDS, "passed": passed},
    } | override
    path = folder / "parity.json"
    path.write_text(json.dumps({"schema": 1, "variants": {VARIANT: variant}}))
    return path


def spec(folder: Path, sequence: int = 1, **override: Any) -> BundleSpec:
    tower, table = write_artefacts(folder / "artefacts")
    benchmark = override.pop("benchmark", None) or parity_benchmark(folder, tower)
    values: dict[str, Any] = {
        "model_key": "bioclip-2",
        "image_model": {
            "path": str(tower),
            "format": "onnx",
            "precision": "fp16",
            "parity": {"benchmark": str(benchmark), "variant": VARIANT},
        },
        "text_table": str(table),
        "min_app_version": "0.1.0",
        "sequence": sequence,
        "expires": "2027-02-14",
    }
    return BundleSpec.model_validate(values | override)
