"""Lazy real SAM3 and PlantCLEF predictors, with source- and runtime-bound caches."""

import gc
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import asdict
from functools import cache
from pathlib import Path

from PIL import Image
from pydantic import BaseModel

from weedz.classification.plantclef import LABELS_SHA256, WEIGHTS_SHA256, PlantClassifier
from weedz.discovery.inference import file_sha256
from weedz.segmentation.sam3_image import (
    CHECKPOINT_SHA256,
    CODE_REVISION,
    HF_REVISION,
    Sam3Config,
    Sam3Image,
)
from weedz.species_aggregation import RankedTaxon
from weedz.validation.agri import LIBRARIES, Configuration, installed
from weedz.validation.cocostuff_data import atomic_file
from weedz.validation.fingerprint import (
    imported_sources,
    pipeline_fingerprint,
    require_stored_orientation,
)
from weedz.validation.registry import RunContext

SAM_PATH = Path("cocostuff/models") / HF_REVISION / "sam3.pt"
PLANT_PATH = Path("inat2021/models/plantclef/plantclef2024.safetensors")
LABEL_PATH = Path("inat2021/models/plantclef/species_id_mapping.txt")
SAM_CONFIG = Sam3Config()
MAX_BYTES = 160_000_000
BATCH_SIZE = 8
TOP_K = 5
type ProposalPredictor = Callable[[Path], list[dict]]
type ClassifierPredictor = Callable[[list[Image.Image]], list[list[RankedTaxon]]]


def model_inputs(root: Path, *, species: bool = False) -> dict[str, str]:
    expected = {SAM_PATH: CHECKPOINT_SHA256}
    if species:
        expected.update({PLANT_PATH: WEIGHTS_SHA256, LABEL_PATH: LABELS_SHA256})
    for path, digest in expected.items():
        if not (root / path).is_file() or file_sha256(root / path) != digest:
            raise ValueError(f"Model checksum mismatch: {path}")
    return {str(path): digest for path, digest in expected.items()}


def identity(adapter: str, *settings: object) -> str:
    libraries = tuple(name for name in LIBRARIES if installed(name) != "not installed")
    return pipeline_fingerprint(
        imported_sources(Path(f"validation/{adapter}.py")), libraries, *settings
    )


def sam_configuration() -> Configuration:
    return {
        **{
            f"sam3_{name}": value for name, value in asdict(SAM_CONFIG).items() if name != "prompts"
        },
        "sam3_prompts": ", ".join(SAM_CONFIG.prompts),
        "sam3_code_revision": CODE_REVISION,
        "sam3_source_byte_budget": MAX_BYTES,
        "proposal_order": "prompt order then descending concept score; no cross-prompt suppression",
    }


def sam_predictor(context: RunContext, adapter: str) -> ProposalPredictor:
    if context.device != "cuda:0":
        raise ValueError("SAM3 requires --device cuda:0")
    model_inputs(context.data_root)
    stamp = identity(adapter, CHECKPOINT_SHA256, asdict(SAM_CONFIG), MAX_BYTES, context.device)
    root = context.cache_dir / "agri" / f"sam3-{adapter}-{stamp}"

    @cache
    def model() -> Sam3Image:
        return Sam3Image.load(
            context.data_root / SAM_PATH, SAM_CONFIG, root, max_source_bytes=MAX_BYTES
        )

    def predict(path: Path) -> list[dict]:
        require_stored_orientation(path)
        digest = file_sha256(path)
        target = root / f"{digest}.json"
        if target.is_file():
            return json.loads(target.read_text())["regions"]
        result = model().screen(path)
        if result["status"] not in {"ok", "empty"}:
            raise RuntimeError(f"SAM3 failed on {path.name}: {result['status']}")
        with atomic_file(target) as stream:
            stream.write(json.dumps({"regions": result["regions"]}, allow_nan=False).encode())
        return result["regions"]

    return predict


def plant_predictor(context: RunContext) -> ClassifierPredictor:
    @cache
    def model() -> PlantClassifier:
        return PlantClassifier.load(
            context.data_root / PLANT_PATH, context.data_root / LABEL_PATH, context.device
        )

    def predict(images: list[Image.Image]) -> list[list[RankedTaxon]]:
        return [
            [RankedTaxon.model_validate(row) for row in rank]
            for rank in model().predict(images, top_k=TOP_K)
        ]

    return predict


def cache_key(*settings: object) -> str:
    return hashlib.sha256(json.dumps(settings, sort_keys=True, default=str).encode()).hexdigest()


def release_cuda() -> None:
    gc.collect()
    importlib.import_module("torch").cuda.empty_cache()


class ProposalBatch(BaseModel):
    regions: list[list[dict]]
    runtime: dict[str, str]


def proposal_batch(context: RunContext, adapter: str, images: list[Path]) -> ProposalBatch:
    """Optionally isolate SAM3's incompatible runtime from the classifier runtime."""
    executable = os.environ.get("WEEDZ_SAM3_PYTHON")
    if executable and Path(executable).resolve() != Path(sys.executable).resolve():
        payload = {
            "data_root": str(context.data_root),
            "cache_dir": str(context.cache_dir),
            "device": context.device,
            "adapter": adapter,
            "images": [str(p) for p in images],
        }
        environment = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
        with tempfile.TemporaryDirectory(prefix="weedz-agri-sam3-") as private:
            output = Path(private) / "evidence.json"
            subprocess.run(
                [executable, "-m", "weedz.validation.agri_models", str(output)],
                input=json.dumps(payload),
                text=True,
                check=True,
                env=environment,
            )
            return ProposalBatch.model_validate_json(output.read_text())
    predict = sam_predictor(context, adapter)
    regions = [predict(path) for path in images]
    del predict
    release_cuda()
    return ProposalBatch(
        regions=regions,
        runtime={f"sam3_runtime_{name}_version": installed(name) for name in LIBRARIES},
    )


def _worker() -> None:
    payload = json.load(sys.stdin)
    context = RunContext(Path(payload["data_root"]), Path(payload["cache_dir"]), payload["device"])
    # The child is already in the selected runtime; avoid spawning another interpreter.
    os.environ.pop("WEEDZ_SAM3_PYTHON", None)
    result = proposal_batch(context, payload["adapter"], [Path(p) for p in payload["images"]])
    Path(sys.argv[1]).write_text(result.model_dump_json())


if __name__ == "__main__":
    _worker()
