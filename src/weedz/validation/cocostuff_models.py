"""Lazy, resumable adapters for the actual Weedz vegetation models."""

import importlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from PIL import Image, ImageOps

from weedz.discovery.inference import file_sha256
from weedz.discovery.vegetation import (
    MODEL_FILES,
    MODEL_REVISION,
    VegetationScreener,
    vegetation_fraction,
)
from weedz.segmentation.sam3_image import CHECKPOINT_SHA256, HF_REVISION, Sam3Config, Sam3Image
from weedz.validation.cocostuff_data import IMAGE_ARCHIVE, atomic_file
from weedz.validation.fingerprint import (
    SAM3_SOURCES,
    SEGFORMER_SOURCES,
    pipeline_fingerprint,
    require_stored_orientation,
)
from weedz.validation.registry import RunContext

SEGFORMER = Path("cocostuff/models") / MODEL_REVISION
SAM3 = Path("cocostuff/models") / HF_REVISION / "sam3.pt"
SAM_CONFIG = Sam3Config()
# This module turns model output into the cached evidence, so it is part of the cache key.
ADAPTER_SOURCES = (Path("validation/cocostuff_models.py"),)
type FractionPredictor = Callable[[Path], float]
type SamPredictor = Callable[[Path], SamPrediction]


@dataclass(frozen=True)
class SamPrediction:
    presence_score: float
    regions: list[dict]


def model_inputs(data_root: Path, *, presence: bool) -> dict[str, str]:
    """Verify the model files on disk and return their hashes for the result's inputs.

    A complete prediction cache never loads the models, so this is where they are checked.
    """
    expected = {SAM3: CHECKPOINT_SHA256}
    if presence:
        expected.update({SEGFORMER / name: digest for name, digest in MODEL_FILES.items()})
    for path, digest in expected.items():
        if not (data_root / path).is_file() or file_sha256(data_root / path) != digest:
            raise ValueError(f"COCO-Stuff model checksum mismatch for {path}")
    return {path.as_posix(): digest for path, digest in expected.items()}


def segformer_predictor(context: RunContext) -> FractionPredictor:
    snapshot = context.data_root / SEGFORMER
    fingerprint = pipeline_fingerprint(
        (*SEGFORMER_SOURCES, *ADAPTER_SOURCES),
        ("torch", "transformers", "pillow", "numpy"),
        "segformer-fp32-v1",
        MODEL_REVISION,
        MODEL_FILES,
        IMAGE_ARCHIVE.sha256,
        context.device,
    )
    output = context.cache_dir / "cocostuff" / f"segformer-{fingerprint}"

    @cache
    def model() -> VegetationScreener:
        return VegetationScreener.load(snapshot, context.device)

    def predict(image_path: Path) -> float:
        result = output / (image_path.stem + ".json")
        if result.is_file():
            return float(json.loads(result.read_text()))
        with Image.open(image_path) as image:
            score = vegetation_fraction(model().predict(ImageOps.exif_transpose(image)))
        with atomic_file(result) as file:
            file.write(json.dumps(score, allow_nan=False).encode())
        return score

    return predict


def sam_predictor(context: RunContext) -> SamPredictor:
    if context.device != "cuda:0":
        raise ValueError("The Weedz SAM3 runtime requires --device cuda:0")
    checkpoint = context.data_root / SAM3
    libraries = ("torch", "numpy", "pillow")
    sources = (*SAM3_SOURCES, *ADAPTER_SOURCES)
    fingerprint = pipeline_fingerprint(sources, libraries, CHECKPOINT_SHA256)
    root = context.cache_dir / "cocostuff" / f"sam3-{fingerprint}"

    @cache
    def model() -> Sam3Image:
        return Sam3Image.load(checkpoint, SAM_CONFIG, root)

    def predict(path: Path) -> SamPrediction:
        require_stored_orientation(path)
        result = model().screen(path)
        if result["status"] in {"failed", "partial"}:
            failures = [
                (row["prompt"], row.get("failure_type"))
                for row in result["prompts"]
                if row["status"] == "failed"
            ]
            raise RuntimeError(f"SAM3 failed on COCO image {path.stem}: {failures}")
        presence_score = max(
            (
                float(score)
                for prompt in result["prompts"]
                for score in prompt["raw_top_concept_scores_before_retention"]
            ),
            default=0.0,
        )
        return SamPrediction(presence_score, result["regions"])

    return predict


def release_cuda() -> None:
    importlib.import_module("torch").cuda.empty_cache()
