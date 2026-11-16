"""Read an existing public experiment without changing its data or human reviews."""

import hashlib
import io
import json
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image

from weedz.annotation.credits import photo_credit
from weedz.annotation.label_studio import Mode, label_config, model_version, task
from weedz.annotation.serialization import NONFINITE_POLICY, result_json
from weedz.contract import Annotation, Media, Rights, Sample
from weedz.discovery.records import Photo
from weedz.rights_profiles import (
    PUBLIC_PROFILE,
    RightsProfile,
    require_source_rights,
    rights_profile_fields,
)


def _read(source: Path, run_id: str) -> tuple[dict[str, Any], list[sqlite3.Row]]:
    database = source / "discovery.sqlite3"
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("BEGIN")
        run = db.execute("SELECT status,model FROM runs WHERE id=?", (run_id,)).fetchone()
        if run is None or run["status"] != "completed":
            raise ValueError("Export requires an existing completed source run")
        rows = db.execute(
            "SELECT record,scores FROM photos WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
        if not rows:
            raise ValueError("Source run has no photos")
        return json.loads(run["model"]), rows


def _output(source: Path, output: Path) -> Path:
    if output.exists() or output.is_symlink():
        raise ValueError("Choose a new output directory; existing artifacts are preserved")
    output = output.resolve()
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Annotation output must be independent of the source")
    if any((parent / ".git").exists() for parent in (output, *output.parents)):
        raise ValueError("Annotation images and masks must stay outside Git")
    return output


def _photo(
    source: Path, raw: str, scores: dict[str, Any], rights_profile: RightsProfile = PUBLIC_PROFILE
) -> tuple[Photo, bytes, tuple[int, int]]:
    record = json.loads(raw)
    if record.get("cohort") not in {"incidental", "reference", "lookalike"}:
        raise ValueError(
            "Only licensed public source photos are supported; device reports are excluded"
        )
    photo = Photo.model_validate(record)
    require_source_rights(
        Rights(
            media_license=photo.photo_license,
            metadata_license=photo.observation_license,
            attribution=photo.attribution,
            license_source=photo.source_url,
        ),
        rights_profile,
    )
    path = (source / photo.image_path).resolve()
    if not path.is_relative_to(source):
        raise ValueError("Source image escapes its experiment directory")
    encoded = path.read_bytes()
    if hashlib.sha256(encoded).hexdigest() != photo.sha256:
        raise ValueError("Source image checksum mismatch")
    with Image.open(io.BytesIO(encoded)) as image:
        if image.width * image.height > 40_000_000:
            raise ValueError("Source image exceeds experiment geometry limits")
        image.load()
        if image.format != "PNG" or image.mode != "RGB" or image.info or image.getexif():
            raise ValueError("Export requires the experiment's metadata-free upright RGB PNG")
        size = image.size
    if (scores.get("width"), scores.get("height")) != size:
        raise ValueError("Model geometry does not match the source image")
    return (
        photo.model_copy(
            update={
                "latitude": None,
                "longitude": None,
                "positional_accuracy_m": None,
                "coordinate_status": "missing",
            }
        ),
        encoded,
        size,
    )


def _sample(
    photo: Photo,
    size: tuple[int, int],
    model: dict[str, Any],
    masks: list[tuple[str, bytes]],
    run_id: str,
    image_prefix: str,
) -> Sample:
    return Sample(
        id=f"inaturalist:{photo.id}",
        source="inaturalist",
        source_id=photo.id,
        snapshot=run_id,
        captured_on=photo.observed_on,
        rights=Rights(
            media_license=photo.photo_license,
            metadata_license=photo.observation_license,
            attribution=photo.attribution,
            license_source=photo.source_url,
        ),
        media=Media(
            uri=f"images/{image_prefix}/{photo.sha256}.png",
            sha256=photo.sha256,
            width=size[0],
            height=size[1],
            format="PNG",
        ),
        original_label=photo.original_taxon,
        tasks=frozenset({"inference"}),
        annotations=tuple(
            Annotation(
                id=f"proposal-{i}",
                supervision="dense_mask",
                label="unknown",
                mask_uri=f"private/masks/{digest}.png",
                origin="model",
                model=model_version("sam-bioclip", model),
            )
            for i, (digest, _) in enumerate(masks)
        ),
    )


def export_label_studio(
    source: Path,
    run_id: str,
    output: Path,
    *,
    mode: Mode = "assisted",
    image_prefix: str = "corpus",
    rights_profile: RightsProfile = PUBLIC_PROFILE,
) -> dict[str, Any]:
    if mode not in {"assisted", "blind"}:
        raise ValueError("Choose assisted or blind mode")
    prefix = PurePosixPath(image_prefix)
    if (
        not image_prefix
        or prefix.is_absolute()
        or any(part in {".", ".."} for part in image_prefix.split("/"))
        or "\\" in image_prefix
        or ":" in image_prefix
    ):
        raise ValueError("Choose a relative image prefix with a real storage subdirectory")
    source = source.resolve()
    output = _output(source, output)
    model, rows = _read(source, run_id)
    json.dumps(model, allow_nan=False)
    prepared = []
    for row in rows:
        scores = json.loads(row["scores"])
        photo, encoded, size = _photo(source, row["record"], scores, rights_profile)
        imported, masks = task(photo.id, photo.sha256, scores, model, size, mode, image_prefix)
        imported["data"]["photo_credit"] = photo_credit(
            photo.attribution, photo.photo_license, photo.observation_license, photo.source_url
        )
        prepared.append((photo, encoded, size, scores, imported, masks))
    output.mkdir(parents=True, exist_ok=False)
    try:
        (output / "images" / image_prefix).mkdir(parents=True)
        private = output / "private"
        private.mkdir(mode=0o700)
        tasks, provenance = [], []
        for photo, encoded, size, scores, imported, masks in prepared:
            (output / "images" / image_prefix / f"{photo.sha256}.png").write_bytes(encoded)
            for digest, png in masks:
                (private / "masks").mkdir(exist_ok=True)
                (private / "masks" / f"{digest}.png").write_bytes(png)
            tasks.append(imported)
            provenance.append(
                {
                    "external_id": imported["meta"]["external_id"],
                    "source_run_id": run_id,
                    "photo": photo.model_dump(),
                    "scores": scores,
                    "sample": _sample(photo, size, model, masks, run_id, image_prefix).model_dump(
                        mode="json"
                    ),
                }
            )
        (output / "tasks.json").write_text(
            json.dumps(tasks, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
        )
        (output / "label-config.xml").write_text(label_config(mode), encoding="utf-8")
        document = {
            **rights_profile_fields(rights_profile),
            "nonfinite_result_policy": NONFINITE_POLICY,
            "schema_version": 1,
            "source_run_id": run_id,
            "mode": mode,
            "model": model,
            "mask_transform": (
                "Original low-resolution RGBA alpha > 0; "
                "nearest-neighbour expansion to source dimensions; official SDK RLE"
            ),
            "interpretation": (
                "Predictions only, never human truth. "
                "The curated source corpus is not an independent holdout."
            ),
            "photos": provenance,
        }
        (private / "provenance.json").write_text(result_json(document) + "\n", encoding="utf-8")
        files = {
            str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.rglob("*"))
            if path.is_file()
        }
        receipt = {
            **rights_profile_fields(rights_profile),
            "schema_version": 1,
            "mode": mode,
            "image_prefix": image_prefix,
            "task_count": len(tasks),
            "files": files,
        }
        (output / "manifest.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )
        return receipt
    except BaseException:
        shutil.rmtree(output)
        raise
