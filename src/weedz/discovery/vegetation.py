"""Vegetation coverage for review intake, separate from weed identification."""

import hashlib
import importlib
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

MODEL_REPOSITORY = "nvidia/segformer-b2-finetuned-ade-512-512"
MODEL_REVISION = "de01bae28967510f9ddd496c60a969357195400c"
WEIGHTS_SHA256 = "187ca07bea003a5717c63d04ea90b07f33cd033c0ebf44b4b89fce5070d6c8f3"
MODEL_FILES = {
    "pytorch_model.bin": WEIGHTS_SHA256,
    "config.json": "ee7400840fdb1e5045f0b2eba78bf053df8e33a309c4acec31705a48c8cc5c00",
    "preprocessor_config.json": "8039d1d210abaa7117ad78e58cdfd6141a2ec72c03dae891b3cd76737e422c6c",
}
# The source PNG labels are one-based. The model indices are zero-based.
VEGETATION_INDICES = (4, 9, 17, 66, 72)
VEGETATION_NAMES = ("tree", "grass", "plant", "flower", "palm")


def vegetation_mask(labels: np.ndarray) -> np.ndarray:
    if (
        labels.ndim != 2
        or not labels.size
        or not np.issubdtype(labels.dtype, np.integer)
        or labels.min() < 0
        or labels.max() >= 150
    ):
        raise ValueError("Expected a nonempty ADE20K label grid with indices 0–149")
    return np.isin(labels, VEGETATION_INDICES)


def vegetation_fraction(labels: np.ndarray) -> float:
    return float(vegetation_mask(labels).mean())


@dataclass(frozen=True)
class IntakePhoto:
    sample_id: str
    fraction: float

    def __post_init__(self) -> None:
        if not self.sample_id or not math.isfinite(self.fraction) or not 0 <= self.fraction <= 1:
            raise ValueError("Expected a source identity and finite vegetation fraction in [0, 1]")


def rank_for_review(photos: Iterable[IntakePhoto]) -> list[IntakePhoto]:
    """Rank for preflight while retaining every score, including zeros for audits."""
    ranked = sorted(photos, key=lambda photo: (-photo.fraction, photo.sample_id))
    if len({photo.sample_id for photo in ranked}) != len(ranked):
        raise ValueError("Duplicate vegetation screening identity")
    return ranked


class VegetationScreener:
    def __init__(self, model: Any, processor: Any, device: str) -> None:
        self.model = model
        self.processor = processor
        self.device = device

    @classmethod
    def load(cls, snapshot: Path, device: str) -> "VegetationScreener":
        for name, expected in MODEL_FILES.items():
            with (snapshot / name).open("rb") as source:
                if hashlib.file_digest(source, "sha256").hexdigest() != expected:
                    raise ValueError(f"SegFormer vegetation model checksum mismatch for {name}")
        transformers = importlib.import_module("transformers")
        model = transformers.SegformerForSemanticSegmentation.from_pretrained(
            snapshot, local_files_only=True, use_safetensors=False
        )
        names = tuple(model.config.id2label[index].split(",", 1)[0] for index in VEGETATION_INDICES)
        if model.config.num_labels != 150 or names != VEGETATION_NAMES:
            raise ValueError("SegFormer ADE20K label mapping mismatch")
        processor = transformers.AutoImageProcessor.from_pretrained(
            snapshot, local_files_only=True, use_fast=False
        )
        return cls(model.to(device).float().eval(), processor, device)

    def predict(self, image: Image.Image) -> np.ndarray:
        torch = importlib.import_module("torch")
        inputs = self.processor(images=image.convert("RGB"), return_tensors="pt")
        with torch.inference_mode():
            logits = self.model(pixel_values=inputs.pixel_values.to(self.device)).logits
            labels = logits[0].argmax(dim=0).cpu().numpy()
        return np.asarray(labels)
