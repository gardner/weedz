"""ImageWeeds v2 boxes from the two official Weed-AI mirror contexts."""

import json
import math
from io import BytesIO
from pathlib import Path

from PIL import Image

from weedz.contract import Annotation, Completeness, Media, Rights, Sample
from weedz.labelled.archive import SourceArchive
from weedz.labelled.publication import close_batch, digest, json_bytes, output_namespace, publish

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
        key = native.removeprefix("weed:")
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


def _sample(source: SourceArchive, image: dict, native: dict, crop: str, output: Path) -> Sample:
    name = image["file_name"]
    raw = source.read(f"images/{name}", maximum_bytes=20_000_000)
    with Image.open(BytesIO(raw)) as pixels:
        if pixels.format != "JPEG" or pixels.getexif().get(274, 1) != 1:
            raise ValueError("Source box frame requires an upright original JPEG")
        if (
            pixels.size != (image["width"], image["height"])
            or pixels.width * pixels.height > 40_000_000
        ):
            raise ValueError("Image dimensions differ from source annotations or exceed budget")
        pixels.load()
        pixel_sha = digest(pixels.convert("RGB").tobytes())
    uri = f"images/{name}"
    publish(output / uri, raw)
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
                media_sha256=digest(raw),
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
        rights=Rights(
            media_license="CC-BY-4.0",
            metadata_license="CC-BY-4.0",
            attribution=f"Rai et al., ImageWeeds v2, {DOI}",
            license_source=DOI,
        ),
        media=Media(
            uri=uri, sha256=digest(raw), width=image["width"], height=image["height"], format="JPEG"
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
            "native_agcontext_id": str(image["agcontext_id"]),
            "annotation_granularity": "publisher manual box; individual identity unverified",
            "native_annotations_sha256": digest(json_bytes(native)),
            "decoded_pixel_sha256": pixel_sha,
            "original_encoded_sha256": digest(raw),
            "format_profile": "standalone external benchmark original upright JPEG; "
            "not public canonical PNG admission",
            "modifications": "none; original encoded bytes and metadata retained privately",
            "split": "publisher split unavailable; descriptive diagnostics only",
        },
    )


def prepare(archive: Path, output: Path, *, crop: str, limit: int) -> str:
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
        samples = [_sample(source, image, native, crop, output) for image in images]
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
                "count": limit,
                "source_family": "ImageWeeds v2; soybean and maize are not independent datasets",
            },
        )
