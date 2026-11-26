"""Margin-native canonical BioCLIP inference; source labels never enter its prompts."""

import io
import json
import math
import tempfile
from importlib.metadata import version
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from weedz.discovery.encoder_backend import PROFILE, cosine_scores
from weedz.discovery.inference import (
    COMPARISONS,
    LABELS,
    MODELS,
    RANKING_REVISION,
    Screener,
    featureless,
    prompt,
    region_boxes,
    square_view,
    summarize_scores,
)
from weedz.discovery.records import SPECIES
from weedz.segmentation.pipeline import identify_views

KIND = "bioclip-margin-cuda-v1"
POLICY = "finite positive recognized watchlist margin; otherwise Unknown; never verified presence"


def _number(value: Any, lower: float, upper: float) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper


def candidate(summary: dict) -> str:
    if summary.get("best_species") in SPECIES and _number(summary.get("margin"), 0, 2):
        return summary["best_species"] if summary["margin"] > 0 else "Unknown"
    return "Unknown"


def validate_summary(value: dict) -> None:
    rows = value.get("species")
    if not isinstance(rows, list) or [row.get("name") for row in rows] != list(SPECIES):
        raise ValueError("BioCLIP summary requires the ordered complete watchlist")
    for row in [value, *rows]:
        if not _number(row.get("similarity"), -1, 1) or not _number(row.get("margin"), -2, 2):
            raise ValueError("Invalid finite BioCLIP cosine or margin")
    best = max(rows, key=lambda row: row["margin"])
    if any(
        value.get(key) != best[name]
        for key, name in [
            ("best_species", "name"),
            ("similarity", "similarity"),
            ("margin", "margin"),
        ]
    ):
        raise ValueError("BioCLIP summary best target disagrees")


def validate_scores(value: dict, *, frame: bool) -> None:
    validate_summary(value)
    raw = np.asarray(value.get("window_similarities"), dtype=np.float32)
    columns = len(SPECIES) + len(COMPARISONS)
    if raw.ndim != 2 or raw.shape[1] != columns or not np.isfinite(raw).all():
        raise ValueError("Invalid BioCLIP raw comparison matrix")
    if not len(raw) or (np.abs(raw) > 1.000001).any():
        raise ValueError("Invalid BioCLIP raw cosine range")
    boxes = value.get("window_boxes") if frame else [(0, 0, 1, 1)]
    if not isinstance(boxes, list) or len(boxes) != len(raw):
        raise ValueError("Incomplete BioCLIP window geometry")
    excluded = value.get("featureless_windows", []) if frame else []
    eligible = [index not in excluded for index in range(len(raw))]
    if not eligible[0]:
        raise ValueError("BioCLIP whole frame must remain eligible")
    expected = summarize_scores(raw, boxes, list(SPECIES) + COMPARISONS, len(SPECIES), eligible)
    for key in (
        ("best_species", "similarity", "margin", "box")
        if frame
        else ("best_species", "similarity", "margin")
    ):
        if value[key] != expected[key]:
            raise ValueError("BioCLIP raw comparison aggregation disagrees")
    _validate_species(value["species"], expected["species"], frame)


def _validate_species(actual_rows, expected_species, frame):
    for actual, reference in zip(actual_rows, expected_species, strict=True):
        if any(
            actual.get(key) != reference[key]
            for key in (
                ("name", "similarity", "margin", "box")
                if frame
                else ("name", "similarity", "margin")
            )
        ):
            raise ValueError("BioCLIP species comparison aggregation disagrees")


def validate_frame_geometry(
    value: dict, size: tuple[int, int], encoded: bytes | None = None
) -> None:
    boxes = [list(box) for box in region_boxes(*size)]
    if value.get("window_boxes") != boxes or (value.get("width"), value.get("height")) != size:
        raise ValueError("BioCLIP frame geometry differs from source pixels")
    excluded = value.get("featureless_windows")
    if not isinstance(excluded, list) or any(
        type(i) is not int or not 1 <= i < len(boxes) for i in excluded
    ):
        raise ValueError("Invalid BioCLIP featureless-window geometry")
    if excluded != sorted(set(excluded)):
        raise ValueError("Duplicate or unordered featureless windows")
    if encoded is not None:
        with Image.open(io.BytesIO(encoded)) as image:
            expected = [
                i
                for i, box in enumerate(boxes)
                if i and featureless(image.crop((box[0], box[1], box[2], box[3])))
            ]
        if excluded != expected:
            raise ValueError("BioCLIP featureless eligibility differs from source pixels")


def identity(metadata: dict, kind: str) -> dict:
    required = {
        "classifier_kind": KIND,
        "backend_profile": PROFILE,
        "device": "cuda:0",
        "scoring_device": "cpu",
        "precision": "float32",
        "ranking_revision": RANKING_REVISION,
        "subject_policy": "None for every canonical sample; source taxonomy never supplied",
        "score_kind": "watchlist_cosine_margin_uncalibrated",
        "assignment_policy": POLICY,
        "subject_prompt": None,
        "prompts": [prompt(label) for label in LABELS],
        "math_policy": {"cuda_matmul_tf32": False, "cudnn_tf32": False, "autocast": False},
    }
    if any(metadata.get(key) != expected for key, expected in required.items()):
        raise ValueError("BioCLIP GPU margin identity disagrees")
    model = metadata.get("model_key")
    if model not in MODELS or metadata.get("revision") != MODELS[model]["revision"]:
        raise ValueError("Unknown pinned BioCLIP model")
    if not isinstance(metadata.get("weights_sha256"), str) or len(metadata["weights_sha256"]) != 64:
        raise ValueError("Missing BioCLIP weight identity")
    if kind not in {"frame", "regions"} or metadata.get("scope") != kind:
        raise ValueError("BioCLIP supports frame and regions only")
    if not metadata.get("embedding_cache", {}).get("preprocessing_sha256"):
        raise ValueError("Missing BioCLIP preprocessing identity")
    if kind == "regions":
        from weedz.batches.profiles import sam_identity

        sam_identity(metadata["proposer"])
        if metadata.get("views") != ["tight", "masked", "context"]:
            raise ValueError("Incomplete BioCLIP crop-view policy")
    _encoder_versions(metadata)
    return json.loads(json.dumps(metadata, allow_nan=False))


def _encoder_versions(metadata: dict) -> None:
    versions = metadata.get("encoder_runtime")
    if not isinstance(versions, dict) or set(versions) != {
        "torch",
        "torchvision",
        "pillow",
        "open_clip_torch",
    }:
        raise ValueError("Incomplete BioCLIP encoder runtime identity")
    if any(not isinstance(value, str) or not value.strip() for value in versions.values()):
        raise ValueError("Invalid BioCLIP encoder runtime version")


def runtime(metadata: dict) -> dict:
    identity(metadata, metadata["scope"])
    return {
        "status": "recorded",
        "framework": "OpenCLIP",
        **{
            key: metadata[key]
            for key in (
                "backend_profile",
                "device",
                "scoring_device",
                "precision",
                "math_policy",
                "cuda",
                "cudnn",
                "gpu",
                "numpy",
                "encoder_runtime",
            )
        },
    }


class BioClipClassifier:
    def __init__(self, screener: Any) -> None:
        self.screener = screener
        self.metadata = {
            **screener.metadata,
            "classifier_kind": KIND,
            "pipeline_name": "BioCLIP GPU margins",
            "subject_policy": "None for every canonical sample; source taxonomy never supplied",
            "score_kind": "watchlist_cosine_margin_uncalibrated",
            "assignment_policy": POLICY,
            "subject_prompt": None,
            "encoder_runtime": {
                name: version(name)
                for name in ("torch", "torchvision", "pillow", "open_clip_torch")
            },
            "frame_policy": (
                "Existing letterboxed whole-frame and overlapping tiles; "
                "featureless tiles cannot win"
            ),
            "region_policy": "Existing tight/masked/context views, each whole crop letterboxed",
        }

    @classmethod
    def load(cls, cache_dir: Path, model: str = "bioclip-2") -> "BioClipClassifier":
        return cls(Screener.load(cache_dir, model=model, backend=PROFILE))

    def view_similarities(self, images: list[Image.Image]) -> np.ndarray:
        """Fixed-prompt similarities for one letterboxed view per supplied image."""
        if not 1 <= len(images) <= 16:
            raise ValueError("BioCLIP view scoring requires one to 16 images")
        screener = self.screener
        with screener.torch.inference_mode():
            batch = screener.torch.stack(
                [screener.transform(square_view(image, (0, 0, *image.size))) for image in images]
            )
            features = screener.model.encode_image(batch, normalize=True)
        return cosine_scores(screener, features, screener.text)

    def profile_metadata(self, kind: str, proposer: dict | None = None) -> dict:
        metadata = {**self.metadata, "scope": kind}
        if kind == "regions":
            from weedz.batches.profiles import sam_identity

            if proposer is None:
                raise ValueError("Regional BioCLIP profile requires SAM metadata")
            metadata.update(proposer=sam_identity(proposer), views=["tight", "masked", "context"])
        return identity(metadata, kind)

    def frame(self, encoded: bytes) -> dict:
        # Screen exactly the already-verified snapshot through the existing public API.
        with tempfile.TemporaryDirectory(prefix="weedz-bioclip-input-") as private:
            path = Path(private) / "image.png"
            path.write_bytes(encoded)
            result = self.screener.screen(path, subject=None)
        with Image.open(io.BytesIO(encoded)) as image:
            result["window_boxes"] = [list(box) for box in region_boxes(*image.size)]
        result.pop(
            "embedding_cache", None
        )  # Cache hit/miss is execution detail, not model evidence.
        validate_scores(result, frame=True)
        return result

    def regions(self, views: dict[str, Image.Image]) -> dict:
        result = identify_views(self.screener, views, None, include_raw=True)
        for value in result.values():
            validate_scores(value, frame=False)
        return result
