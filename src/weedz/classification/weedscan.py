"""Independent CPU adapter for CSIRO's released WeedScan488 probability model."""

import hashlib
import importlib
import json
from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

CLASS_COUNT = 488
RELEASE = "csiro61320-v1"
WEIGHTS_SHA256 = "5b564b88511211b63e5a6a50101779c34b940e040fd0c099e75fcd97146cc0dc"
LABELS_SHA256 = "315474e605c2bd5543e8241f256ebd63ff336ee3f6dc14f72571017391767fa4"
MAX_ARTIFACT_BYTES = 100_000_000
MAX_RESIZED_PIXELS = 40_000_000
INPUT_POLICY = (
    "Already-upright RGB pixels; no adapter EXIF rotation; Pillow BICUBIC short edge480; "
    "floor long edge; centre480 nearest ties-even; ImageNet RGB; NCHW float32"
)


def verified_bytes(path: Path, expected_sha256: str) -> bytes:
    with path.open("rb") as stream:
        encoded = stream.read(MAX_ARTIFACT_BYTES + 1)
    if len(encoded) > MAX_ARTIFACT_BYTES:
        raise ValueError("WeedScan artifact exceeds byte cap")
    if hashlib.sha256(encoded).hexdigest() != expected_sha256:
        raise ValueError("WeedScan artifact checksum mismatch")
    return encoded


def class_labels(encoded: bytes, expected_count: int | None = None) -> tuple[str, ...]:
    count = CLASS_COUNT if expected_count is None else expected_count
    rows = json.loads(encoded)
    if not isinstance(rows, list) or len(rows) != count:
        raise ValueError("Invalid WeedScan class mapping size")
    indexed = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid WeedScan class mapping row")
        index, name = row.get("Embedding"), row.get("ScientificName")
        if (
            type(index) is not int
            or index in indexed
            or not isinstance(name, str)
            or not name.strip()
        ):
            raise ValueError("Invalid WeedScan class mapping index/name")
        indexed[index] = name
    if set(indexed) != set(range(count)) or len(set(indexed.values())) != count:
        raise ValueError("Invalid WeedScan class mapping order/duplicates")
    return tuple(indexed[index] for index in range(count))


def preprocess(image: Image.Image) -> np.ndarray:
    width, height = image.size
    size = (480, int(height * 480 / width)) if width <= height else (int(width * 480 / height), 480)
    if size[0] * size[1] > MAX_RESIZED_PIXELS:
        raise ValueError("WeedScan preprocessing exceeds resized pixel cap")
    resized = image.convert("RGB").resize(size, Image.Resampling.BICUBIC)
    left, top = int(round((size[0] - 480) / 2)), int(round((size[1] - 480) / 2))
    pixels = np.asarray(resized.crop((left, top, left + 480, top + 480)), dtype=np.float32)
    mean = np.array([123.675, 116.28, 103.53], dtype=np.float32)
    std = np.array([58.395, 57.12, 57.375], dtype=np.float32)
    return np.ascontiguousarray(((pixels - mean) / std).transpose(2, 0, 1)[None])


def rank_scores(scores: np.ndarray, labels: tuple[str, ...], k: int) -> list[dict]:
    if type(k) is not int or not 1 <= k <= len(labels):
        raise ValueError("Invalid WeedScan top-k")
    if (
        scores.shape != (len(labels),)
        or not np.isfinite(scores).all()
        or (scores < 0).any()
        or (scores > 1).any()
        or abs(float(scores.sum()) - 1) > 1e-3
    ):
        raise ValueError("Invalid WeedScan probability output")
    indices = np.argsort(-scores, kind="stable")[:k]
    return [
        {
            "taxon": labels[index],
            "score": float(scores[index]),
            "score_kind": "closed_set_softmax_uncalibrated",
        }
        for index in indices
    ]


def _validate_session(session: Any) -> None:
    inputs, outputs = session.get_inputs(), session.get_outputs()
    if session.get_providers() != ["CPUExecutionProvider"]:
        raise ValueError("Unexpected WeedScan provider")
    if (
        len(inputs) != 1
        or inputs[0].type != "tensor(float)"
        or len(inputs[0].shape) != 4
        or inputs[0].shape[1] != 3
        or any(
            type(value) is int and value != expected
            for value, expected in zip(inputs[0].shape, (1, 3, 480, 480), strict=True)
        )
    ):
        raise ValueError("Unexpected WeedScan input contract")
    if (
        len(outputs) != 1
        or outputs[0].type != "tensor(float)"
        or len(outputs[0].shape) != 2
        or outputs[0].shape[1] != CLASS_COUNT
        or type(outputs[0].shape[0]) is int
        and outputs[0].shape[0] != 1
    ):
        raise ValueError("Unexpected WeedScan output contract")


class WeedScanClassifier:
    def __init__(self, session: Any, labels: tuple[str, ...], metadata: dict) -> None:
        self.session, self.labels, self.metadata = session, labels, metadata
        self.on_scores: Callable[[np.ndarray], None] | None = None

    @classmethod
    def load(cls, checkpoint: Path, labels_path: Path) -> "WeedScanClassifier":
        weights = verified_bytes(checkpoint, WEIGHTS_SHA256)
        labels = class_labels(verified_bytes(labels_path, LABELS_SHA256))
        ort = importlib.import_module("onnxruntime")
        options = ort.SessionOptions()
        options.intra_op_num_threads, options.inter_op_num_threads = 4, 1
        session = ort.InferenceSession(
            weights, sess_options=options, providers=["CPUExecutionProvider"]
        )
        _validate_session(session)
        return cls(
            session,
            labels,
            {
                "model": "WeedScan488 CSIRO MobileNetV2 ORT",
                "pipeline_name": "WeedScan488",
                "supported_profiles": ["frame"],
                "frame_input_policy": INPUT_POLICY,
                "release": RELEASE,
                "collection": "https://data.csiro.au/collection/csiro:61320",
                "weights_sha256": WEIGHTS_SHA256,
                "labels_sha256": LABELS_SHA256,
                "class_count": CLASS_COUNT,
                "licence": "CC-BY-NC-4.0",
                "device": "cpu",
                "precision": "float32",
                "onnxruntime": version("onnxruntime"),
                "numpy": version("numpy"),
                "pillow": version("pillow"),
                "providers": session.get_providers(),
                "intra_op_threads": 4,
                "inter_op_threads": 1,
                "preprocessing": {
                    "short_edge": 480,
                    "crop": [480, 480],
                    "interpolation": "Pillow BICUBIC",
                    "resize_rounding": "floor",
                    "crop_rounding": "nearest ties-even",
                    "exif_rotation": False,
                    "mean": [123.675, 116.28, 103.53],
                    "std": [58.395, 57.12, 57.375],
                    "layout": "NCHW RGB float32",
                },
                "score_kind": "closed_set_softmax_uncalibrated",
                "limitations": [
                    "Closed-set weed taxonomy; no non-plant rejection or calibrated confidence",
                    "Genus and subspecies labels retained exactly as released",
                    "Canonical inputs must already be upright; JPEG oracle uses stored pixels",
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
            if output.shape != (1, CLASS_COUNT) or output.dtype != np.float32:
                raise ValueError("Unexpected WeedScan output shape/type")
            rows.append(rank_scores(output[0], self.labels, top_k))
            if self.on_scores is not None:
                self.on_scores(output[0].copy())
        return rows
