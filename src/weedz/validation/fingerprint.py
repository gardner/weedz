"""Cache identities that change whenever the pipeline code or its libraries change.

Checks cache raw model evidence so a full run can resume. Keying that cache by
the code that produced it means a pipeline change can't reuse stale evidence.
"""

import hashlib
import json
from collections.abc import Iterable
from importlib.metadata import version
from pathlib import Path

from PIL import Image

PACKAGE_ROOT = Path(__file__).resolve().parents[1]

SAM3_SOURCES = (
    Path("segmentation/sam3_image.py"),
    Path("segmentation/regions.py"),
    Path("segmentation/ingress.py"),
    Path("segmentation/artifacts.py"),
)
SEGFORMER_SOURCES = (Path("discovery/vegetation.py"),)
EXIF_ORIENTATION = 0x0112


def require_stored_orientation(path: Path) -> None:
    """Refuse a photo whose EXIF rotation would put SAM3's output in a different frame.

    SAM3 reads photos EXIF-upright, while the public labels use the stored pixels.
    """
    with Image.open(path) as image:
        orientation = image.getexif().get(EXIF_ORIENTATION, 1)
    if orientation != 1:
        raise ValueError(f"{path.name} has EXIF orientation {orientation}; labels would not align")


def pipeline_fingerprint(
    sources: Iterable[Path],
    packages: Iterable[str],
    *settings: object,
    root: Path = PACKAGE_ROOT,
) -> str:
    """Hash the named source files, library versions and settings into a short key."""
    digests = [
        (path.as_posix(), hashlib.sha256((root / path).read_bytes()).hexdigest())
        for path in sources
    ]
    payload = [
        digests,
        {package: version(package) for package in packages},
        settings,
    ]
    encoded = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(encoded).hexdigest()[:20]
