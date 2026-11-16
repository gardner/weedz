"""Read-only encoded/pixel deduplication of explicit local manifest cohorts."""

from collections import Counter, defaultdict
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from weedz.contract import Sample
from weedz.labelled.pixels import pixel_sha256
from weedz.labelled.publication import digest


def audit(manifests: tuple[Path, ...]) -> dict:
    encoded: dict[str, list[str]] = defaultdict(list)
    pixels: dict[str, list[str]] = defaultdict(list)
    sources: Counter[str] = Counter()
    origins: Counter[str] = Counter()
    originals: dict[str, list[str]] = defaultdict(list)
    pins = []
    for manifest in manifests:
        raw = manifest.read_bytes()
        pins.append({"manifest": str(manifest.resolve()), "sha256": digest(raw)})
        for line in raw.splitlines():
            sample = Sample.model_validate_json(line)
            encoded_sha, pixel_sha = verified_asset(sample, manifest.parent)
            encoded[encoded_sha].append(sample.id)
            pixels[pixel_sha].append(sample.id)
            sources[sample.source] += 1
            origins.update(f"{a.origin}:{a.supervision}" for a in sample.annotations)
            original = sample.context.get("original_encoded_sha256") or sample.context.get(
                "source_image_sha256"
            )
            if original:
                originals[original].append(sample.id)
    return {
        "schema_version": 1,
        "manifests": pins,
        "samples": sum(sources.values()),
        "by_source": dict(sorted(sources.items())),
        "annotation_origins": dict(sorted(origins.items())),
        "unique_encoded_assets": len(encoded),
        "unique_decoded_assets": len(pixels),
        "encoded_duplicates": _duplicates(encoded),
        "decoded_duplicates": _duplicates(pixels),
        "original_encoded_duplicates": _duplicates(originals),
        "pixel_identity": "SHA256 of RGB:WIDTHxHEIGHT NUL prefix plus upright RGB bytes",
        "limits": "Exact duplicates only; near duplicates and independent sites are unassessed",
    }


def verified_asset(sample: Sample, root: Path) -> tuple[str, str]:
    path = (root / sample.media.uri).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Audit media must be confined to its explicit manifest root")
    with path.open("rb") as stream:
        raw = stream.read(160_000_001)
    if len(raw) > 160_000_000 or digest(raw) != sample.media.sha256:
        raise ValueError("Audit image byte budget or checksum mismatch")
    with Image.open(BytesIO(raw)) as image:
        if image.width * image.height > 40_000_000:
            raise ValueError("Audit pixel budget exceeded")
        if image.size != (sample.media.width, sample.media.height):
            raise ValueError("Audit source dimensions differ from manifest")
        pixel_sha = pixel_sha256(ImageOps.exif_transpose(image))
    return digest(raw), pixel_sha


def _duplicates(groups: dict[str, list[str]]) -> list[dict]:
    return [
        {"sha256": sha, "sample_ids": sorted(ids)}
        for sha, ids in sorted(groups.items())
        if len(ids) > 1
    ]
