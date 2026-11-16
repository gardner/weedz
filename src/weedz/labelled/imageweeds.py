"""ImageWeeds v2 boxes from the two official Weed-AI mirror contexts."""

import json
import math
from pathlib import Path

from weedz.contract import Annotation, Completeness, Media, Rights, Sample
from weedz.labelled.archive import SourceArchive
from weedz.labelled.images import prepare_image
from weedz.labelled.publication import close_batch, digest, output_namespace, publish

DOI = "https://doi.org/10.17632/8kjcztbjz2.2"
LICENCE = "https://creativecommons.org/licenses/by/4.0/"
PROFILES = {
    "soybean": (
        "cfe6e919-6ddd-4b4e-aa63-58483841a11f",
        "3cb63ffdac4c8ece9e08a33389395585fcd4ea380ee3b933bdd549df55c1ecc2",
        81,
    ),
    "maize": (
        "1a9e04c8-80c3-41f1-a7af-a9d3f39d0feb",
        "361f5adad959ca35f8cf4dc7769077eb1a75930d28c4c0a7247d937496bb6bbb",
        94,
    ),
}
TAXA = {
    "erigeroncanadensis": "Erigeron canadensis",
    "bassiascoparia": "Bassia scoparia",
    "amaranthusretroflexus": "Amaranthus retroflexus",
    "ambrosiaartemisiifolia": "Ambrosia artemisiifolia",
    "amaranthustuberculatus": "Amaranthus tuberculatus",
}


def source_boxes(image: dict, rows: list[dict], categories: list[dict]) -> tuple[Annotation, ...]:
    names = {item["id"]: item["name"] for item in categories}
    if len(names) != len(categories):
        raise ValueError("Duplicate source category identity")
    result = []
    for row in rows:
        if row["image_id"] != image["id"]:
            continue
        native = names.get(row["category_id"], "")
        key = "".join(native.removeprefix("weed:").split())
        if key not in TAXA:
            raise ValueError("Unknown source category; taxonomy mapping must be explicit")
        x, y, width, height = row["bbox"]
        if (
            not all(math.isfinite(value) for value in (x, y, width, height))
            or min(x, y) < 0
            or min(width, height) <= 0
            or x + width > image["width"]
            or y + height > image["height"]
        ):
            raise ValueError("Source box outside image bounds")
        result.append(
            Annotation(
                id=str(row["id"]),
                supervision="box",
                taxon=TAXA[key],
                label="present",
                box=(x, y, x + width, y + height),
                origin="source",
                note=f"Native category {row['category_id']}: {native}; publisher manual box.",
            )
        )
    return tuple(result)


def source_rights(native: dict, image: dict) -> Rights:
    metadata = native["info"]["metadata"]
    licences = {row["id"]: row["url"] for row in native["licenses"]}
    if metadata["license"] != LICENCE or licences.get(image["license"]) != LICENCE:
        raise ValueError("Image and metadata must separately match published CC BY4 rights")
    creators = ", ".join(row["name"] for row in metadata["creator"])
    if not creators:
        raise ValueError("Publisher creator attribution is missing")
    return Rights(
        media_license="CC-BY-4.0",
        metadata_license="CC-BY-4.0",
        creator=creators,
        attribution=f"{creators}; ImageWeeds v2; {DOI}; CC BY4",
        license_source=DOI,
    )


def _sample(
    source: SourceArchive,
    image: dict,
    native: dict,
    crop: str,
    output: Path,
    image_format: str,
    native_sha256: str,
) -> Sample:
    rights = source_rights(native, image)
    name = image["file_name"]
    raw = source.read(f"images/{name}", maximum_bytes=20_000_000)
    prepared = prepare_image(raw, (image["width"], image["height"]), image_format)
    filename = str(Path(name).with_suffix(".png")) if prepared.output_format == "PNG" else name
    uri = f"images/{filename}"
    publish(output / uri, prepared.encoded)
    annotations = source_boxes(image, native["annotations"], native["categories"])
    uuid, archive_sha, _ = PROFILES[crop]
    categories = tuple(sorted({note.taxon for note in annotations if note.taxon}))
    # Coverage is unknown: published boxes do not establish all-target absence elsewhere.
    completeness = (
        ()
        if not categories
        else (
            Completeness(
                id=f"{image['id']}-coverage",
                media_sha256=digest(prepared.encoded),
                task="detection",
                taxa=categories,
                status="unknown",
                origin="source",
                evidence={"publisher": DOI},
            ),
        )
    )
    return Sample(
        id=f"imageweeds:{crop}/{name}",
        source="imageweeds",
        source_id=f"{crop}/{name}",
        snapshot=f"{uuid}:v2:{archive_sha}",
        rights=rights,
        media=Media(
            uri=uri,
            sha256=digest(prepared.encoded),
            width=image["width"],
            height=image["height"],
            format=prepared.output_format,
        ),
        view="nadir",
        scale="patch",
        tasks=frozenset({"detection", "inference"}),
        annotations=annotations,
        completeness=completeness,
        groups={
            "source_dataset": "imageweeds-v2",
            "agcontext": f"imageweeds:{crop}:{image['agcontext_id']}",
            "source_image": f"imageweeds:{name}",
        },
        context={
            "source_url": f"https://weed-ai.sydney.edu.au/datasets/{uuid}",
            "original_dataset": DOI,
            "native_image_id": str(image["id"]),
            "encoded_format": prepared.source_format,
            "source_frame_index": "0",
            "source_frame_count": str(prepared.source_frames),
            "native_agcontext_id": str(image["agcontext_id"]),
            "annotation_granularity": "publisher manual box; individual identity unverified",
            "native_annotations_sha256": native_sha256,
            "decoded_pixel_sha256": prepared.pixel_sha256,
            "original_encoded_sha256": digest(raw),
            "format_profile": image_format,
            "modifications": (
                "metadata-free lossless RGB PNG; no resize; primary frame0"
                if image_format == "lossless-rgb-png"
                else "none; original encoded bytes and metadata retained privately"
            ),
            "split": "publisher split unavailable; descriptive diagnostics only",
        },
    )


def quarantine(native: dict) -> dict[str, str]:
    excluded = {}
    for image in native["images"]:
        try:
            source_boxes(image, native["annotations"], native["categories"])
        except ValueError as error:
            if str(error) != "Source box outside image bounds":
                raise
            excluded[image["file_name"]] = str(error) + "; entire image withheld, no clipping"
    return excluded


def prepare(
    archive: Path, output: Path, *, crop: str, limit: int, image_format: str = "lossless-rgb-png"
) -> str:
    uuid, archive_sha, count = PROFILES[crop]
    if not 1 <= limit <= count:
        raise ValueError(f"ImageWeeds {crop} limit must be between 1 and {count}")
    output = output_namespace(output, archive.parent)
    with SourceArchive(archive, archive_sha) as source:
        raw = source.read("weedcoco.json", maximum_bytes=10_000_000)
        native = json.loads(raw)
        if len(native["images"]) != count:
            raise ValueError("Pinned source image count differs")
        images = sorted(native["images"], key=lambda image: image["id"])[:limit]
        excluded = quarantine(native)
        samples = [
            _sample(source, image, native, crop, output, image_format, digest(raw))
            for image in images
            if image["file_name"] not in excluded
        ]
        source.verify()
        publish(output / "native/weedcoco.json", raw)
        return close_batch(
            output,
            samples,
            {
                "source": DOI,
                "mirror_uuid": uuid,
                "mirror_version": 2,
                "archive_sha256": archive_sha,
                "native_annotations_sha256": digest(raw),
                "licence": LICENCE,
                "selected_source_images": limit,
                "retained_images": len(samples),
                "image_format_profile": image_format,
                "quarantined_source_images": excluded,
                "source_family": "ImageWeeds v2; soybean and maize are not independent datasets",
            },
        )
