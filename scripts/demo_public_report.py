"""Build capture evidence only from checksum-verified, attributed public pilot pixels."""

import base64
import hashlib
import io
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from weedz.discovery.inference import MODELS
from weedz.discovery.sharing import refuse_unadmitted, terms

SOURCE_RUN = "nelson-tasman-3e62ad801459"
SOURCE_PHOTO = "inat-250240131-447484684"


def clean_public_image(pilot: Path, record: dict[str, Any]) -> bytes:
    image = (pilot / record["image_path"]).resolve()
    if not image.is_relative_to((pilot / "images").resolve()) or not image.is_file():
        raise ValueError("Capture image must be within the public image cache")
    raw = image.read_bytes()
    if hashlib.sha256(raw).hexdigest() != record.get("sha256"):
        raise ValueError("Public source image checksum differs from its recorded evidence")
    with Image.open(io.BytesIO(raw)) as source:
        upright = ImageOps.exif_transpose(source).convert("RGB")
        clean = Image.new("RGB", upright.size)
        clean.paste(upright)
        output = io.BytesIO()
        clean.save(output, format="JPEG", quality=95)
    return output.getvalue()


def source_capture(pilot: Path) -> dict[str, Any]:
    pilot = pilot.resolve()
    with closing(
        sqlite3.connect((pilot / "discovery.sqlite3").as_uri() + "?mode=ro", uri=True)
    ) as db:
        row = db.execute(
            "SELECT p.record,p.scores,r.model FROM photos p JOIN runs r ON r.id=p.run_id "
            "WHERE p.run_id=? AND p.id=? AND r.status='completed'",
            (SOURCE_RUN, SOURCE_PHOTO),
        ).fetchone()
    if row is None:
        raise ValueError("The documented completed public capture evidence is missing")
    record, scores, stamp = (json.loads(value) for value in row)
    if record["photo_license"] != "cc-by":
        raise ValueError("Only the attributed public CC BY source is allowed")
    refuse_unadmitted(record["photo_license"], record.get("observation_license", ""))
    model_key = next(
        (
            key
            for key, model in MODELS.items()
            if model["repo"] == stamp["model"] and model["revision"] == stamp["revision"]
        ),
        None,
    )
    if model_key is None:
        raise ValueError("The source model revision is not in the supported capture registry")
    encoded_image = clean_public_image(pilot, record)
    report = {
        "schema_version": 1,
        "app_version": "0.1.0+capture",
        "candidate": {"taxon": scores["best_species"], "score": scores["margin"]},
        "model": {
            "model_key": model_key,
            "revision": stamp["revision"],
            "ranking_revision": stamp["ranking_revision"],
        },
        "consent": {
            "wording_version": "2026-11",
            "image": True,
            "location": False,
            "licence": record["photo_license"],
            "credit": record["attribution"],
            "uses": ["review"],
        },
        "image": base64.b64encode(encoded_image).decode(),
    }
    return {
        "report": report,
        "source_provenance": {
            "source_run_id": SOURCE_RUN,
            "source_photo_id": SOURCE_PHOTO,
            "source_image_sha256": record["sha256"],
            "report_image_sha256": hashlib.sha256(encoded_image).hexdigest(),
            "rights": terms(record),
            "source_model": stamp,
            "modifications": "Original encoded source checksum verified; EXIF orientation "
            "applied; fresh RGB canvas strips metadata; JPEG re-encoding at quality95.",
        },
    }


def source_report(pilot: Path) -> dict[str, Any]:
    """Keep the intake payload API separate from capture-only public credits."""
    return source_capture(pilot)["report"]
