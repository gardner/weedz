"""Lazy, resumable adapters for the actual Weedz vegetation models."""

import importlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from PIL import Image, ImageOps

from weedz.discovery.vegetation import (
    MODEL_FILES,
    MODEL_REVISION,
    VegetationScreener,
    vegetation_fraction,
)
from weedz.segmentation.sam3_image import CHECKPOINT_SHA256, HF_REVISION, Sam3Config, Sam3Image
from weedz.validation.cocostuff_data import IMAGE_ARCHIVE, atomic_file
from weedz.validation.fingerprint import SAM3_SOURCES, SEGFORMER_SOURCES, pipeline_fingerprint
from weedz.validation.registry import RunContext

SEGFORMER = Path("cocostuff/models") / MODEL_REVISION
SAM3 = Path("cocostuff/models") / HF_REVISION / "sam3.pt"
SAM_CONFIG = Sam3Config()
type FractionPredictor = Callable[[Path], float]
type SamPredictor = Callable[[Path], SamPrediction]


@dataclass(frozen=True)
class SamPrediction:
    presence_score: float
    regions: list[dict]


def model_inputs(*, presence: bool) -> dict[str, str]:
    inputs = {SAM3.as_posix(): CHECKPOINT_SHA256}
    if presence:
        inputs.update({str(SEGFORMER / name): digest for name, digest in MODEL_FILES.items()})
    return inputs


def segformer_predictor(context: RunContext) -> FractionPredictor:
    snapshot = context.data_root / SEGFORMER
    fingerprint = pipeline_fingerprint(
        SEGFORMER_SOURCES,
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
    fingerprint = pipeline_fingerprint(SAM3_SOURCES, libraries, CHECKPOINT_SHA256)
    root = context.cache_dir / "cocostuff" / f"sam3-{fingerprint}"

    @cache
    def model() -> Sam3Image:
        return Sam3Image.load(checkpoint, SAM_CONFIG, root)

    def predict(path: Path) -> SamPrediction:
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
