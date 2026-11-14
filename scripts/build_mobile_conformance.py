"""Build tiny image-processing goldens for a phone verifier, without loading a model.

Run `uv run python scripts/build_mobile_conformance.py`. These images are synthetic,
contain no private photos, and cover EXIF orientation, square padding and the strict
featureless threshold. Expected crops are generated from the decoded source image.
"""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from weedz.discovery.inference import FEATURELESS_STD, featureless, region_boxes, square_view

DEFAULT_OUTPUT = Path("mobile/test/fixtures/model_conformance")


def _sources(folder: Path) -> list[Path]:
    y, x = np.indices((12, 8))
    pixels = np.stack((x * 30, y * 20, (x + y) * 12), axis=2).astype(np.uint8)
    orientation = folder / "orientation-6.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # Rotate the decoded 8x12 image clockwise into 12x8.
    Image.fromarray(pixels).save(orientation, quality=95, subsampling=0, exif=exif)
    sources = [orientation]
    y, x = np.indices((10, 10))
    for amplitude in (7, 8, 9):
        path = folder / f"std-{amplitude}.png"
        grey = (120 + ((x + y) % 2 * 2 - 1) * amplitude).astype(np.uint8)
        Image.fromarray(grey).convert("RGB").save(path)
        sources.append(path)
    return sources


def build(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    cases = []
    for source in _sources(folder):
        with Image.open(source) as original:
            orientation = original.getexif().get(0x0112, 1)
            image = ImageOps.exif_transpose(original).convert("RGB")
        upright = f"{source.stem}-upright.png"
        image.save(folder / upright)
        windows = []
        for index, box in enumerate(region_boxes(*image.size)):
            crop = image.crop(box)
            square = f"{source.stem}-window-{index}.png"
            square_view(image, box).save(folder / square)
            windows.append(
                {
                    "box": list(box),
                    "square": square,
                    "greyscale_population_std": repr(float(np.asarray(crop.convert("L")).std())),
                    "featureless": featureless(crop),
                    "eligible": index == 0 or not featureless(crop),
                }
            )
        cases.append(
            {
                "source": source.name,
                "exif_orientation": orientation,
                "upright": upright,
                "upright_size": list(image.size),
                "windows": windows,
            }
        )
    manifest = {"schema": 1, "featureless_std_below": FEATURELESS_STD, "cases": cases}
    (folder / "expected.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build(parser.parse_args().output)
