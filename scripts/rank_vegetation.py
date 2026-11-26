"""Rank a source-verified canonical photo manifest for visual review preflight."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageOps

from weedz.discovery.vegetation import (
    MODEL_REPOSITORY,
    MODEL_REVISION,
    WEIGHTS_SHA256,
    IntakePhoto,
    VegetationScreener,
    rank_for_review,
    vegetation_fraction,
)
from weedz.manifest import read_manifest


def _sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--media-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args()
    root = args.media_root.resolve(strict=True)
    manifest_sha = _sha256(args.manifest)
    samples = read_manifest(args.manifest, manifest_sha)
    model = VegetationScreener.load(args.model, args.device)
    ranked = []
    images = {}
    for sample in samples:
        path = (root / sample.media.uri).resolve(strict=True)
        if not path.is_relative_to(root) or _sha256(path) != sample.media.sha256:
            raise ValueError(f"Media identity differs from the manifest for {sample.id}")
        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original)
            if image.size != (sample.media.width, sample.media.height):
                raise ValueError(f"Media dimensions differ from the manifest for {sample.id}")
            ranked.append(IntakePhoto(sample.id, vegetation_fraction(model.predict(image))))
        images[sample.id] = sample.media.sha256

    report = {
        "source_manifest_sha256": manifest_sha,
        "model": MODEL_REPOSITORY,
        "revision": MODEL_REVISION,
        "weights_sha256": WEIGHTS_SHA256,
        "input_config_sha256": _sha256(args.model / "preprocessor_config.json"),
        "purpose": "Vegetation coverage ranking for visual preflight",
        "rows": [
            {
                "sample_id": row.sample_id,
                "image_sha256": images[row.sample_id],
                "fraction": row.fraction,
            }
            for row in rank_for_review(ranked)
        ],
    }
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, allow_nan=False)
        output.write("\n")


if __name__ == "__main__":
    main()
