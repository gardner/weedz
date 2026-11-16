"""Source-only ImageWeeds evidence, including geometrically invalid annotation aliases."""

import json
from dataclasses import dataclass
from pathlib import Path

from weedz.contract import Annotation, Rights
from weedz.labelled.archive import SourceArchive
from weedz.labelled.images import prepare_image
from weedz.labelled.imageweeds import PROFILES, quarantine, source_boxes, source_rights
from weedz.labelled.publication import digest


@dataclass(frozen=True)
class NativeImage:
    sample_id: str
    encoded_sha256: str
    pixel_sha256: str
    annotation_source_sha256: str
    annotations: tuple[Annotation, ...] | None
    annotation_count: int
    rights: Rights
    snapshot: str
    error: str | None


def inventory(source_dir: Path) -> dict[str, NativeImage]:
    records: dict[str, NativeImage] = {}
    for crop, (uuid, archive_sha, count) in PROFILES.items():
        with SourceArchive(source_dir / f"imageweeds-{crop}.zip", archive_sha) as source:
            raw = source.read("weedcoco.json", maximum_bytes=10_000_000)
            native = json.loads(raw)
            if len(native["images"]) != count:
                raise ValueError("Pinned native image count differs")
            invalid = quarantine(native)
            for image in native["images"]:
                record = _image(
                    source, image, native, crop, invalid, digest(raw), f"{uuid}:v2:{archive_sha}"
                )
                if record.sample_id in records:
                    raise ValueError("Duplicate native source identity")
                records[record.sample_id] = record
            source.verify()
    return records


def _image(
    source: SourceArchive,
    image: dict,
    native: dict,
    crop: str,
    invalid: dict,
    annotation_sha: str,
    snapshot: str,
) -> NativeImage:
    rights = source_rights(native, image)
    raw = source.read(f"images/{image['file_name']}", maximum_bytes=20_000_000)
    prepared = prepare_image(raw, (image["width"], image["height"]), "original-jpeg")
    error = invalid.get(image["file_name"])
    annotations = (
        None if error else source_boxes(image, native["annotations"], native["categories"])
    )
    return NativeImage(
        sample_id=f"imageweeds:{crop}/{image['file_name']}",
        encoded_sha256=digest(raw),
        pixel_sha256=prepared.pixel_sha256,
        annotation_source_sha256=annotation_sha,
        annotations=annotations,
        annotation_count=sum(row["image_id"] == image["id"] for row in native["annotations"]),
        rights=rights,
        snapshot=snapshot,
        error=error,
    )
