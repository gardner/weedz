"""Resumable classifiers over verified canonical samples, without creating human labels."""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Protocol

from PIL import Image

from weedz.consent import refusal
from weedz.contract import Sample, require_task
from weedz.discovery.inference import file_sha256, region_boxes, square_view
from weedz.manifest import read_manifest, write_atomic

Profile = Literal["frame", "tiles"]


class Classifier(Protocol):
    metadata: dict[str, Any]

    def predict(self, images: list[Image.Image], top_k: int = 5) -> list[list[dict]]: ...


def _metadata(model: Classifier, profile: Profile) -> dict:
    if profile == "frame":
        return {
            **model.metadata,
            "input_policy": (
                "EXIF-upright source pixels; timm resize and centre crop; "
                "no source taxonomy supplied"
            ),
        }
    return {
        **model.metadata,
        "input_policy": (
            "Letterboxed full image and overlapping square 60%-side tiles; "
            "fixed geometry revision 2; retain all top-five alternatives per view"
        ),
        "aggregation": (
            "Per-taxon maximum closed-set softmax over views; "
            "uncalibrated ranking, not probabilities"
        ),
        "ranking_revision": 1,
    }


def _source(sample: Sample, root: Path) -> Path:
    require_task(sample, "inference")
    consent = sample.rights.consent
    if consent and (reason := refusal(consent.uses, consent.withdrawn_at, "training")):
        raise ValueError(reason)
    path = (root / sample.media.uri).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Source media escapes the declared root")
    if not sample.media.sha256 or file_sha256(path) != sample.media.sha256:
        raise ValueError("Source media checksum mismatch")
    return path


def _view_predictions(
    rows: list[dict], work: list[tuple[dict, tuple, Image.Image]], model: Classifier
) -> None:
    for start in range(0, len(work), 32):
        part = work[start : start + 32]
        result = model.predict([item[2] for item in part])
        for (row, box, _), topk in zip(part, result, strict=True):
            row["views"].append({"box": box, "topk": topk})
    for row in rows:
        candidates: dict[str, dict] = {}
        for view in row["views"]:
            for candidate in view["topk"]:
                if candidate["score"] > candidates.get(candidate["taxon"], {}).get("score", -1):
                    candidates[candidate["taxon"]] = {
                        **candidate,
                        "score_kind": "maximum_closed_set_softmax_across_views_uncalibrated",
                    }
        row["topk"] = sorted(candidates.values(), key=lambda item: (-item["score"], item["taxon"]))[
            :5
        ]


def _predict(
    samples: list[Sample], root: Path, model: Classifier, profile: Profile, model_version: str
) -> list[dict]:
    rows = []
    group_size = 32 if profile == "frame" else 4
    for start in range(0, len(samples), group_size):
        group = samples[start : start + group_size]
        images, part, work = [], [], []
        for sample in group:
            with Image.open(_source(sample, root)) as original:
                image = original.convert("RGB")
            key = hashlib.sha256(f"{sample.id}:{sample.media.sha256}".encode()).hexdigest()
            row = {
                "external_id": key,
                "source_id": sample.id,
                "image_sha256": sample.media.sha256,
                "model_version": model_version,
            }
            rows.append(row)
            part.append(row)
            if profile == "frame":
                images.append(image)
            else:
                row["views"] = []
                work.extend(
                    (row, box, square_view(image, box)) for box in region_boxes(*image.size)
                )
        if profile == "frame":
            for row, topk in zip(part, model.predict(images), strict=True):
                row["topk"] = topk
        else:
            _view_predictions(part, work, model)
    return rows


def classify_batch(
    manifest: Path, media_root: Path, output: Path, model: Classifier, profile: Profile = "frame"
) -> dict:
    if profile not in {"frame", "tiles"}:
        raise ValueError("Unknown classification profile")
    manifest_sha = file_sha256(manifest)
    samples = read_manifest(manifest, manifest_sha)
    if not 1 <= len(samples) <= 1000:
        raise ValueError("Use a nonempty batch of at most 1000 samples")
    # Verify bytes even when a result already exists: a cached score cannot hide changed media.
    for sample in samples:
        _source(sample, media_root)
    metadata = _metadata(model, profile)
    stamp = hashlib.sha256(
        json.dumps(metadata, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    version = f"PlantCLEF {profile} auto-label · {stamp[:12]}"
    if output.exists():
        previous = json.loads(output.read_text())
        if (
            previous.get("manifest_sha256") != manifest_sha
            or previous.get("model_version") != version
        ):
            raise ValueError("Existing classifier batch has different provenance")
        return previous
    rows = _predict(samples, media_root, model, profile, version)
    result = {
        "schema": 1,
        "model": metadata,
        "model_version": version,
        "manifest_sha256": manifest_sha,
        "predictions": rows,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(output, (json.dumps(result, indent=2, allow_nan=False) + "\n").encode())
    return result
