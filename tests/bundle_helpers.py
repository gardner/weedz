"""Small stand-ins for a model bundle: fake artefacts, a parity record and a signing key.

Nothing here downloads or runs a model; the "image tower" is a few random bytes.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from weedz.bundles.manifest import BundleSpec
from weedz.bundles.text_table import prompts, save_table
from weedz.discovery.inference import MODELS
from weedz.discovery.parity import THRESHOLDS

VARIANT = "onnx-fp16"
DIMENSIONS = 4
# What open_clip.get_model_preprocess_cfg reports for a ViT-L/14 tower.
PREPROCESSING = {
    "size": (224, 224),
    "mode": "RGB",
    "mean": (0.48145466, 0.4578275, 0.40821073),
    "std": (0.26862954, 0.26130258, 0.27577711),
    "interpolation": "bicubic",
    "resize_mode": "shortest",
    "fill_color": 0,
}


def write_artefacts(folder: Path, model_key: str = "bioclip-2") -> tuple[Path, Path]:
    """An image tower (random bytes) and a text table with one row per fixed prompt."""
    folder.mkdir(parents=True, exist_ok=True)
    tower = folder / "visual-fp16.onnx"
    tower.write_bytes(b"not really an onnx graph " * 64)
    table = folder / "text.f32"
    rows = [[0.5] * DIMENSIONS for _ in prompts()]
    save_table(table, rows, model_key, "w" * 64, PREPROCESSING)
    return tower, table


def parity_benchmark(
    folder: Path,
    tower: Path,
    passed: bool = True,
    thresholds: dict[str, Any] = THRESHOLDS,
    **override: Any,
) -> Path:
    """A parity benchmark laid out as compare_optimised writes it: thresholds once, at the
    top, and one variant that measured exactly `tower`'s bytes."""
    model = MODELS["bioclip-2"]
    variant = {
        "model": model["repo"],
        "revision": model["revision"],
        "artefact_sha256": hashlib.sha256(tower.read_bytes()).hexdigest(),
        "runtime": {"format": "onnx", "precision": "fp16", "input_dtype": "float16"},
        "parity": {
            "passed": passed,
            "checks": {
                name: {"value": 0, "limit": limit, "passed": True}
                for name, limit in THRESHOLDS["limits"].items()
            },
        },
    } | override
    path = folder / "parity.json"
    benchmark = {"schema": 1, "thresholds": thresholds, "variants": {VARIANT: variant}}
    path.write_text(json.dumps(benchmark))
    return path


def spec(folder: Path, sequence: int = 1, **override: Any) -> BundleSpec:
    tower, table = write_artefacts(folder / "artefacts")
    benchmark = override.pop("benchmark", None) or parity_benchmark(folder, tower)
    values: dict[str, Any] = {
        "model_key": "bioclip-2",
        "image_model": {
            "path": str(tower),
            "parity": {"benchmark": str(benchmark), "variant": VARIANT},
        },
        "text_table": str(table),
        "min_app_version": "0.1.0",
        "sequence": sequence,
        "expires": "2027-02-14",
    }
    return BundleSpec.model_validate(values | override)
