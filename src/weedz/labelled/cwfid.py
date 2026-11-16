"""CWFID functional semantic masks; no inferred species or plant instances."""

from io import BytesIO
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from weedz.contract import Annotation, Completeness, Media, Rights, Sample
from weedz.labelled.archive import SourceArchive
from weedz.labelled.publication import close_batch, digest, output_namespace, publish

REVISION = "36290d0912a032f0bd1a5678ed55457ddafde217"
ARCHIVE_SHA256 = "5a5f178e7d87a55b5d03fbd6047f09114255e6bdec609f1b3bed920601a1f1e3"
SOURCE = f"https://github.com/cwfid/dataset/tree/{REVISION}"
TERMS = (
    "All data is subject to copyright and may only be used for non-commercial research. "
    "In case of use please cite our publication."
)


def memberships(number: int, split: dict) -> tuple[str, ...]:
    return tuple(name for name in ("train", "test") if number in split[name])


def png(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def masks(classes: bytes, vegetation: bytes, size: tuple[int, int]) -> dict[str, Image.Image]:
    with Image.open(BytesIO(classes)) as image:
        colours = np.asarray(image.convert("RGB"))
    with Image.open(BytesIO(vegetation)) as image:
        binary = np.asarray(image.convert("L"))
    if colours.shape != (size[1], size[0], 3) or binary.shape != (size[1], size[0]):
        raise ValueError("Source mask geometry differs from image")
    weed = np.all(colours == (255, 0, 0), axis=2)
    crop = np.all(colours == (0, 255, 0), axis=2)
    black = np.all(colours == 0, axis=2)
    if not np.all(weed | crop | black) or not np.all((binary == 0) | (binary == 255)):
        raise ValueError("Unknown source mask colour")
    foreground = binary == 0
    if np.any((weed | crop) & ~foreground):
        raise ValueError("Class-labelled pixels must be vegetation")
    arrays = {
        "weed": weed,
        "crop": crop,
        "vegetation": foreground,
        "assessed": weed | crop,
    }
    return {key: Image.fromarray(array.astype("uint8") * 255) for key, array in arrays.items()}


def _sample(source: SourceArchive, prefix: str, number: int, output: Path, split: dict) -> Sample:
    name = f"{number:03}"
    raw = source.read(f"{prefix}/images/{name}_image.png")
    with Image.open(BytesIO(raw)) as image:
        if image.getexif().get(274, 1) != 1:
            raise ValueError("Annotation orientation is not documented for rotated images")
        image.load()
        clean = Image.frombytes("RGB", image.size, image.convert("RGB").tobytes())
    image_raw = png(clean)
    uri = f"images/{name}.png"
    publish(output / uri, image_raw)
    classes = source.read(f"{prefix}/annotations/{name}_annotation.png")
    vegetation = source.read(f"{prefix}/masks/{name}_mask.png")
    derived = masks(classes, vegetation, clean.size)
    annotations = []
    for category, image in derived.items():
        mask_raw = png(image)
        mask_uri = f"masks/{name}-{category}.png"
        publish(output / mask_uri, mask_raw)
        if category in {"crop", "weed"} and image.getbbox():
            annotations.append(
                Annotation(
                    id=f"{name}-{category}",
                    supervision="sparse_mask",
                    category=category,
                    label="present",
                    mask_uri=mask_uri,
                    mask_sha256=digest(mask_raw),
                    origin="source",
                    note="Expert polygons intersected with publisher NDVI/Otsu vegetation mask; "
                    "partial plant/part regions, not manually traced boundaries.",
                )
            )
    polygon_raw = source.read(f"{prefix}/annotations/{name}_annotation.yaml")
    publish(output / f"native/{name}_annotation.yaml", polygon_raw)
    publish(output / f"native/{name}_annotation.png", classes)
    publish(output / f"native/{name}_vegetation.png", vegetation)
    member = memberships(number, split)
    return Sample(
        id=f"cwfid:{name}",
        source="cwfid",
        source_id=name,
        snapshot=REVISION,
        rights=Rights(
            media_license=TERMS,
            metadata_license=TERMS,
            creator="Sebastian Haug and Jörn Ostermann",
            attribution="Haug and Ostermann (2015), DOI:10.1007/978-3-319-16220-1_8",
            license_source=f"{SOURCE}/README.md",
        ),
        media=Media(
            uri=uri, sha256=digest(image_raw), width=clean.width, height=clean.height, format="PNG"
        ),
        view="nadir",
        scale="patch",
        groups={"source_dataset": "cwfid", "source_image": f"cwfid:{name}"},
        tasks=frozenset({"sparse_segmentation", "inference"}),
        annotations=tuple(annotations),
        context={
            "label_space": "cwfid:functional",
            "annotation_granularity": "partial semantic",
            "sensor_channels": "Red, Near-Infrared, Red (false-colour); not natural RGB",
            "vegetation_reference_uri": f"masks/{name}-vegetation.png",
            "vegetation_reference_sha256": digest(png(derived["vegetation"])),
            "vegetation_reference_method": "NDVI/Otsu threshold fitted on training images",
            "polygon_granularity": "publisher-labelled region; individual identity unverified",
            "source_splits": ",".join(member),
            "heldout_quarantine": str(len(member) != 1).lower(),
            "original_encoded_sha256": digest(raw),
            "native_annotation_sha256": digest(classes),
            "native_polygon_sha256": digest(polygon_raw),
            "assessed_mask_uri": f"masks/{name}-assessed.png",
            "assessed_mask_sha256": digest(png(derived["assessed"])),
            "assessment_rule": "crop/weed coloured pixels only; unlabelled vegetation and "
            "algorithmically inferred background excluded",
            "decoded_pixel_sha256": digest(clean.tobytes()),
            "source_url": SOURCE,
            "release_scope": "private non-commercial research; not public/LS admission",
        },
        completeness=(
            Completeness(
                id=f"{name}-coverage",
                media_sha256=digest(image_raw),
                task="segmentation",
                categories=("crop", "weed"),
                status="partial",
                origin="source",
                evidence={"protocol": f"{SOURCE}/README.md"},
            ),
        ),
    )


def prepare(archive: Path, output: Path, *, limit: int = 60) -> str:
    if not 1 <= limit <= 60:
        raise ValueError("CWFID limit must be between 1 and 60")
    output = output_namespace(output, archive.parent)
    with SourceArchive(archive, ARCHIVE_SHA256) as source:
        prefix = f"dataset-{REVISION}"
        split_raw = source.read(f"{prefix}/train_test_split.yaml")
        split = yaml.safe_load(split_raw)
        samples = [_sample(source, prefix, n, output, split) for n in range(1, limit + 1)]
        source.verify()
        publish(output / "native/train_test_split.yaml", split_raw)
        return close_batch(
            output,
            samples,
            {
                "source": SOURCE,
                "archive_sha256": ARCHIVE_SHA256,
                "revision": REVISION,
                "split_sha256": digest(split_raw),
                "overlapping_split_ids": ["028"],
                "unique_source_images": 60,
                "native_split_memberships": 61,
                "limit": limit,
                "terms": TERMS,
                "annotation_granularity": "partial semantic",
                "sensor_channels": "Red, Near-Infrared, Red (false-colour); not natural RGB",
                "vegetation_reference_method": "NDVI/Otsu threshold fitted on training images",
                "source_protocol": "expert plant/part polygons intersected with NDVI/Otsu mask",
                "paper": "https://doi.org/10.1007/978-3-319-16220-1_8",
                "instance_completeness": "unknown",
            },
        )
