"""Pinned PlantCLEF classifier with broad alternatives, never calibrated weed confidence."""

import importlib
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from weedz.discovery.inference import file_sha256

REPOSITORY = "vincent-espitalier/dino-v2-reg4-with-plantclef2024-weights"
REVISION = "24656bb424790575adcbd7954ceefb1d87ec8b24"
WEIGHTS_SHA256 = "815a8908af8f3ee3c5ebe76030d06925a981b1af5c929f26d7c64f9fecde8ff4"
LABELS_SHA256 = "5891b9ba98c6c5ae7fed925caab252e0bcde82182a077e192a9455d35f083072"
SCORE_KIND = "closed_set_softmax_uncalibrated"


def ranked_species(logits: np.ndarray, labels: tuple[str, ...], k: int) -> list[dict]:
    if logits.ndim != 1 or len(logits) != len(labels) or not labels:
        raise ValueError("Classifier output and class mapping disagree")
    if len(set(labels)) != len(labels) or any(not label.strip() for label in labels):
        raise ValueError("Invalid class mapping")
    if not np.isfinite(logits).all():
        raise ValueError("Classifier logits must be finite")
    if not 1 <= k <= len(labels):
        raise ValueError("Invalid top-k count")
    exp = np.exp(logits.astype(np.float64) - logits.max())
    shares = exp / exp.sum()
    order = np.argsort(-logits, kind="stable")[:k]
    return [
        {"taxon": labels[i], "score": float(shares[i]), "score_kind": SCORE_KIND} for i in order
    ]


class PlantClassifier:
    def __init__(self, model: Any, transform: Any, labels: tuple[str, ...], metadata: dict) -> None:
        self.model, self.transform, self.labels, self.metadata = model, transform, labels, metadata
        self.torch = importlib.import_module("torch")

    @classmethod
    def load(cls, checkpoint: Path, labels_path: Path, device: str = "cpu") -> "PlantClassifier":
        if file_sha256(checkpoint) != WEIGHTS_SHA256:
            raise ValueError("PlantCLEF checkpoint checksum mismatch")
        if file_sha256(labels_path) != LABELS_SHA256:
            raise ValueError("PlantCLEF class mapping checksum mismatch")
        labels = tuple(labels_path.read_text().splitlines())
        if len(labels) != 7806 or len(set(labels)) != 7806:
            raise ValueError("Invalid PlantCLEF class mapping")
        timm = importlib.import_module("timm")
        safe = importlib.import_module("safetensors.torch")
        model = timm.create_model(
            "vit_base_patch14_reg4_dinov2", pretrained=False, num_classes=7806
        )
        model.load_state_dict(safe.load_file(checkpoint), strict=True)
        model.to(device).eval()
        config = timm.data.resolve_model_data_config(model)
        transform = timm.data.create_transform(**config, is_training=False)
        return cls(
            model,
            transform,
            labels,
            {
                "model": "PlantCLEF2024 DINOv2 ViT-B/14 reg4 fully fine-tuned",
                "repository": REPOSITORY,
                "revision": REVISION,
                "weights_sha256": WEIGHTS_SHA256,
                "labels_sha256": LABELS_SHA256,
                "class_count": len(labels),
                "licence": "CC-BY-NC-4.0 (released safetensors conversion)",
                "original_release": "https://zenodo.org/records/10848263",
                "preprocessing": config,
                "device": device,
                "precision": "float32",
                "timm": version("timm"),
                "torch": version("torch"),
                "score_kind": SCORE_KIND,
                "limitations": [
                    "Southwestern European flora; New Zealand native alternatives may be absent",
                    "Closed-set plant classifier has no validated non-plant rejection",
                    "Softmax shares are not calibrated weed identification confidence",
                ],
            },
        )

    def predict(self, images: list[Image.Image], top_k: int = 5) -> list[list[dict]]:
        if not images:
            return []
        if len(images) > 32:
            raise ValueError("Classifier batch exceeds 32-image cap")
        device = self.metadata["device"]
        with self.torch.inference_mode():
            batch = self.torch.stack([self.transform(image) for image in images]).to(device)
            logits = self.model(batch).float().cpu().numpy()
        return [ranked_species(row, self.labels, top_k) for row in logits]
