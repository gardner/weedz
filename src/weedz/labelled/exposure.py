"""Explicit prior-exposure evidence, not inferred independence from absent metadata."""

import json
import re
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from weedz.contract import Sample
from weedz.labelled.pixels import pixel_sha256
from weedz.labelled.publication import digest


def observer_tokens(raw: dict) -> set[str]:
    return {f"id:{raw['user']['id']}", f"login:{raw['user']['login'].casefold()}"}


def additional(paths: tuple[Path, ...]) -> tuple[set[int], set[str], set[str], list[dict]]:
    observations: set[int] = set()
    observers: set[str] = set()
    pixels: set[str] = set()
    pins = []
    for path in paths:
        raw = path.read_bytes()
        if path.suffix == ".jsonl":
            _manifest(raw, path.parent, observations, observers, pixels)
        else:
            _provenance(raw, observations, observers)
        pins.append({"file": path.name, "sha256": digest(raw)})
    return observations, observers, pixels, pins


def _manifest(
    raw: bytes, root: Path, observations: set[int], observers: set[str], pixels: set[str]
) -> None:
    for line in raw.splitlines():
        sample = Sample.model_validate_json(line)
        if sample.source != "inaturalist":
            continue
        match = re.fullmatch(r"(?:inat-)?(\d+)[/-](\d+)", sample.source_id)
        if match is None:
            raise ValueError("Unknown prior iNaturalist source ID representation")
        observations.add(int(match[1]))
        observer = sample.groups.get("observer")
        if observer and observer.startswith("inaturalist:"):
            observers.add("id:" + observer.removeprefix("inaturalist:"))
        image_path = (root / sample.media.uri).resolve()
        if not image_path.is_relative_to(root.resolve()):
            raise ValueError("Prior media must be confined to its explicit manifest root")
        encoded = image_path.read_bytes()
        if digest(encoded) != sample.media.sha256:
            raise ValueError("Prior image checksum mismatch")
        with Image.open(BytesIO(encoded)) as image:
            if image.width * image.height > 40_000_000:
                raise ValueError("Prior image exceeds pixel budget")
            pixels.add(pixel_sha256(ImageOps.exif_transpose(image)))


def _provenance(raw: bytes, observations: set[int], observers: set[str]) -> None:
    record = json.loads(raw)
    for item in record["photos"]:
        photo = item["photo"]
        observations.add(int(photo["observation_id"]))
        observers.add("login:" + photo["observer"].casefold())
