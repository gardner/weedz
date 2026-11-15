"""Independent implementation of the released Waikato ONNX inference contract."""

import hashlib
import importlib
import json
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

from weedz.classification.plantclef import ranked_species

RELEASE = "model-small-onnx-fp32-384-v1.0"
SOURCE_REVISION = "c36d8838f189d64de7dde8037ebb7a606dc39968"
WEIGHTS_SHA256 = "1905b995f53f58cfab8c611c388ff670bab2dcb5019e8cceec0937e9f0291e68"
LABELS_SHA256 = "b2b27faf173e9b0613f3580fdc0b4c380c962341ef1466b4abd55b2bf078882e"
CLASS_COUNT = 14991
INPUT_POLICY = "EXIF-upright RGB; antialiased bilinear short edge416; centre384; no source taxonomy"


def verified_bytes(path: Path, expected_sha256: str) -> bytes:
    encoded = path.read_bytes()
    if hashlib.sha256(encoded).hexdigest() != expected_sha256:
        raise ValueError("Aotearoa artifact checksum mismatch")
    return encoded


def class_labels(encoded: bytes, expected_count: int = CLASS_COUNT) -> tuple[str, ...]:
    data = json.loads(encoded)
    if not isinstance(data, dict) or set(data) != {str(i) for i in range(expected_count)}:
        raise ValueError("Invalid Aotearoa class mapping indices")
    labels = tuple(data[str(i)].get("scientific_name") for i in range(expected_count))
    if any(not isinstance(name, str) or not name.strip() for name in labels):
        raise ValueError("Invalid Aotearoa class mapping names")
    if len(set(labels)) != expected_count:
        raise ValueError("Duplicate Aotearoa class mapping names")
    return labels


def preprocess(image: Image.Image) -> np.ndarray:
    upright = ImageOps.exif_transpose(image).convert("RGB")
    width, height = upright.size
    size = (416, int(416 * height / width)) if width <= height else (int(416 * width / height), 416)
    resized = upright.resize(size, Image.Resampling.BILINEAR)
    # Released application puts the extra pixel on the bottom/right.
    left, top = (size[0] - 384) // 2, (size[1] - 384) // 2
    crop = resized.crop((left, top, left + 384, top + 384))
    pixels = np.asarray(crop, dtype=np.float32) / np.float32(255)
    return np.ascontiguousarray(
        ((pixels - np.float32(0.5)) / np.float32(0.5)).transpose(2, 0, 1)[None]
    )


def rank_logits(logits: np.ndarray, labels: tuple[str, ...], k: int) -> list[dict]:
    return ranked_species(logits, labels, k)


class AotearoaClassifier:
    def __init__(self, session: Any, labels: tuple[str, ...], metadata: dict) -> None:
        self.session, self.labels, self.metadata = session, labels, metadata
        self.on_logits: Callable[[np.ndarray], None] | None = None

    @classmethod
    def load(cls, checkpoint: Path, labels_path: Path) -> "AotearoaClassifier":
        # Create the session from the verified snapshot, never a subsequently reopened path.
        weights = verified_bytes(checkpoint, WEIGHTS_SHA256)
        labels = class_labels(verified_bytes(labels_path, LABELS_SHA256))
        ort = importlib.import_module("onnxruntime")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        session = ort.InferenceSession(
            weights, sess_options=options, providers=["CPUExecutionProvider"]
        )
        inputs, outputs = session.get_inputs(), session.get_outputs()
        if (
            len(inputs) != 1
            or inputs[0].shape != [1, 3, 384, 384]
            or inputs[0].type != "tensor(float)"
        ):
            raise ValueError("Unexpected Aotearoa model input contract")
        if len(outputs) != 1 or outputs[0].shape != [1, CLASS_COUNT]:
            raise ValueError("Unexpected Aotearoa model output contract")
        return cls(
            session,
            labels,
            {
                "model": "Aotearoa Species Classifier EfficientNetV2 small ONNX",
                "pipeline_name": "Aotearoa NZ",
                "supported_profiles": ["frame"],
                "frame_input_policy": INPUT_POLICY,
                "repository": "Waikato/aotearoa-species-classifier",
                "revision": SOURCE_REVISION,
                "release": RELEASE,
                "weights_sha256": WEIGHTS_SHA256,
                "labels_sha256": LABELS_SHA256,
                "class_count": CLASS_COUNT,
                "licence": "CC-BY-NC-4.0",
                "upstream_notices": "timm/tf_efficientnetv2_s.in21k Apache-2.0",
                "precision": "float32",
                "device": "cpu",
                "onnxruntime": version("onnxruntime"),
                "pillow": version("pillow"),
                "numpy": version("numpy"),
                "preprocessing": {
                    "resize_short_edge": 416,
                    "crop": [384, 384],
                    "interpolation": "Pillow antialiased bilinear",
                    "crop_rounding": "floor",
                    "mean": [0.5, 0.5, 0.5],
                    "std": [0.5, 0.5, 0.5],
                    "layout": "NCHW RGB",
                },
                "score_kind": "closed_set_softmax_uncalibrated",
                "limitations": [
                    "Closed-set species classification; animal and fungal outputs remain valid",
                    (
                        "Raw-logit softmax is not calibrated weed confidence; "
                        "upstream temperature not applied"
                    ),
                    "Released full-frame crop only; no validated whole-region policy",
                ],
            },
        )

    def predict(self, images: list[Image.Image], top_k: int = 5) -> list[list[dict]]:
        if len(images) > 32:
            raise ValueError("Classifier batch exceeds 32-image cap")
        rows = []
        for image in images:
            output = self.session.run(None, {self.session.get_inputs()[0].name: preprocess(image)})[
                0
            ]
            if output.shape != (1, CLASS_COUNT):
                raise ValueError("Unexpected Aotearoa output shape")
            rows.append(rank_logits(output[0], self.labels, top_k))
            if self.on_logits is not None:
                self.on_logits(output[0].copy())
        return rows
