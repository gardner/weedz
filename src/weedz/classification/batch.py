"""Resumable classifiers over verified canonical samples, without creating human labels."""

import fcntl
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any, Literal, Protocol

from PIL import Image

from weedz.consent import refusal
from weedz.contract import Sample, require_task
from weedz.discovery import inference
from weedz.discovery.inference import file_sha256, region_boxes, square_view
from weedz.manifest import read_manifest, write_atomic
from weedz.segmentation.artifacts import digest
from weedz.segmentation.regions import MAX_SOURCE_BYTES, MAX_SOURCE_PIXELS

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
        "tile_geometry": {
            "tile_fraction": inference.TILE_FRACTION,
            "max_stride": inference.MAX_STRIDE,
            "max_tiles": inference.MAX_TILES,
            "letterbox": list(inference.LETTERBOX),
            "window_revision": inference.WINDOW_REVISION,
        },
    }


def _source(sample: Sample, root: Path) -> Path:
    require_task(sample, "inference")
    consent = sample.rights.consent
    if consent and (reason := refusal(consent.uses, consent.withdrawn_at, "training")):
        raise ValueError(reason)
    path = (root / sample.media.uri).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Source media escapes the declared root")
    return path


def _snapshot(sample: Sample, root: Path) -> bytes:
    with _source(sample, root).open("rb") as stream:
        encoded = stream.read(MAX_SOURCE_BYTES + 1)
    if len(encoded) > MAX_SOURCE_BYTES:
        raise ValueError("Canonical image exceeds the source byte cap")
    if not sample.media.sha256 or hashlib.sha256(encoded).hexdigest() != sample.media.sha256:
        raise ValueError("Source media checksum mismatch")
    with Image.open(io.BytesIO(encoded)) as image:
        if image.format != "PNG" or image.mode != "RGB":
            raise ValueError("Use canonical upright metadata-free RGB PNG media")
        if image.size != (sample.media.width, sample.media.height):
            raise ValueError("Canonical image geometry disagrees with the manifest")
        if image.width * image.height > MAX_SOURCE_PIXELS:
            raise ValueError("Canonical image exceeds the pixel cap")
        image.load()
        if image.info or image.getexif():
            raise ValueError("Use canonical upright metadata-free RGB PNG media")
    return encoded


def _identity(sample: Sample, version: str) -> dict:
    return {
        "external_id": hashlib.sha256(f"{sample.id}:{sample.media.sha256}".encode()).hexdigest(),
        "source_id": sample.id,
        "image_sha256": sample.media.sha256,
        "model_version": version,
    }


def _check_topk(value: Any) -> None:
    if not isinstance(value, list) or not 1 <= len(value) <= 5:
        raise ValueError("Incomplete cached classifier alternatives")
    names = []
    for row in value:
        if not isinstance(row, dict):
            raise ValueError("Invalid cached classifier alternative")
        taxon, score = row.get("taxon"), row.get("score")
        if not isinstance(taxon, str) or not taxon.strip():
            raise ValueError("Invalid cached classifier taxon")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise ValueError("Invalid cached classifier score")
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Invalid cached classifier score")
        names.append(taxon)
    if len(set(names)) != len(names):
        raise ValueError("Duplicate cached classifier alternatives")


def _verified_result(output: Path, verified_sha: str | None) -> dict:
    with output.open("rb") as stream:
        encoded = stream.read(128_000_001)
    if len(encoded) > 128_000_000:
        raise ValueError("Cached classifier output exceeds the resource cap")
    result = json.loads(encoded)
    if not isinstance(result, dict):
        raise ValueError("Invalid cached classifier result")
    body = {key: value for key, value in result.items() if key != "result_sha256"}
    if "result_sha256" in result:
        if result["result_sha256"] != digest(body):
            raise ValueError("Cached result checksum mismatch")
    elif verified_sha is None or hashlib.sha256(encoded).hexdigest() != verified_sha:
        raise ValueError("Cached result checksum mismatch or missing verified legacy reference")
    return result


def _cached(
    output: Path, header: dict, samples: list[Sample], verified_sha: str | None, profile: Profile
) -> dict:
    result = _verified_result(output, verified_sha)
    if any(digest({key: result.get(key)}) != digest({key: value}) for key, value in header.items()):
        raise ValueError("Existing classifier batch has different provenance")
    rows = result.get("predictions")
    if not isinstance(rows, list) or len(rows) != len(samples):
        raise ValueError("Incomplete cached prediction rows")
    for sample, row in zip(samples, rows, strict=True):
        if not isinstance(row, dict):
            raise ValueError("Invalid cached prediction row")
        expected = _identity(sample, header["model_version"])
        if any(row.get(key) != value for key, value in expected.items()):
            raise ValueError("Cached prediction asset identity mismatch")
        _check_topk(row.get("topk"))
        if profile == "tiles":
            _check_tiles(sample, row)
    return result


def _commit_result(
    output: Path,
    result: dict,
    header: dict,
    samples: list[Sample],
    verified_sha: str | None,
    profile: Profile,
) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.with_suffix(output.suffix + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if output.exists():
            return _cached(output, header, samples, verified_sha, profile)
        write_atomic(output, (json.dumps(result, indent=2, allow_nan=False) + "\n").encode())
    return result


def _aggregate_views(views: list[dict]) -> list[dict]:
    candidates: dict[str, dict] = {}
    for view in views:
        for candidate in view["topk"]:
            if candidate["score"] > candidates.get(candidate["taxon"], {}).get("score", -1):
                candidates[candidate["taxon"]] = {
                    **candidate,
                    "score_kind": "maximum_closed_set_softmax_across_views_uncalibrated",
                }
    return sorted(candidates.values(), key=lambda item: (-item["score"], item["taxon"]))[:5]


def _check_tiles(sample: Sample, row: dict) -> None:
    views = row.get("views")
    width, height = sample.media.width, sample.media.height
    if width is None or height is None:
        raise ValueError("Missing cached tile source geometry")
    boxes = [list(box) for box in region_boxes(width, height)]
    if not isinstance(views, list) or len(views) != len(boxes):
        raise ValueError("Incomplete cached tiled views")
    for view, box in zip(views, boxes, strict=True):
        if not isinstance(view, dict) or view.get("box") != box:
            raise ValueError("Cached tile geometry differs")
        _check_topk(view.get("topk"))
    if row["topk"] != _aggregate_views(views):
        raise ValueError("Cached tile aggregation disagrees with its views")


def _view_predictions(
    rows: list[dict], work: list[tuple[dict, tuple, Image.Image]], model: Classifier
) -> None:
    for start in range(0, len(work), 32):
        part = work[start : start + 32]
        result = model.predict([item[2] for item in part])
        for (row, box, _), topk in zip(part, result, strict=True):
            row["views"].append({"box": list(box), "topk": topk})
    for row in rows:
        row["topk"] = _aggregate_views(row["views"])


def _predict(
    samples: list[Sample], root: Path, model: Classifier, profile: Profile, model_version: str
) -> list[dict]:
    rows = []
    group_size = 32 if profile == "frame" else 4
    for start in range(0, len(samples), group_size):
        group = samples[start : start + group_size]
        images, part, work = [], [], []
        for sample in group:
            with Image.open(io.BytesIO(_snapshot(sample, root))) as original:
                image = original.convert("RGB")
            row = _identity(sample, model_version)
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
    manifest: Path,
    media_root: Path,
    output: Path,
    model: Classifier,
    profile: Profile = "frame",
    *,
    verified_existing_sha256: str | None = None,
) -> dict:
    if profile not in {"frame", "tiles"}:
        raise ValueError("Unknown classification profile")
    manifest_sha = file_sha256(manifest)
    samples = read_manifest(manifest, manifest_sha)
    if not 1 <= len(samples) <= 1000:
        raise ValueError("Use a nonempty batch of at most 1000 samples")
    # Verify bytes even when a result already exists: a cached score cannot hide changed media.
    for sample in samples:
        _snapshot(sample, media_root)
    metadata = json.loads(json.dumps(_metadata(model, profile), allow_nan=False))
    stamp = hashlib.sha256(
        json.dumps(metadata, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    version = f"PlantCLEF {profile} auto-label · {stamp[:12]}"
    header = {
        "schema": 1,
        "model": metadata,
        "model_version": version,
        "manifest_sha256": manifest_sha,
    }
    if output.exists():
        return _cached(output, header, samples, verified_existing_sha256, profile)
    rows = _predict(samples, media_root, model, profile, version)
    body = {**header, "predictions": rows}
    result = {**body, "result_sha256": digest(body)}
    return _commit_result(output, result, header, samples, verified_existing_sha256, profile)
