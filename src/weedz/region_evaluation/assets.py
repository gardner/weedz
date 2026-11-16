"""Read pinned, source-grid ground-truth assets without implicit colour rules."""

import hashlib
import io
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image

MAX_MASK_BYTES = 20 * 1024 * 1024
MAX_MASK_PIXELS = 40_000_000


def read_binary_mask(
    assets_root: Path, uri: str, sha256: str, *, size: tuple[int, int]
) -> NDArray[np.bool_]:
    """Require canonical binary PNG; foreground is 255, never inferred from RGB.

    The verified bytes themselves are decoded, so replacing the original path after
    this read cannot substitute a different mask during evaluation.
    """
    root = assets_root.resolve(strict=True)
    relative = Path(uri)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Mask must use a relative path within its asset root")
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError("Mask escapes its asset root")
    with path.open("rb") as source:
        encoded = source.read(MAX_MASK_BYTES + 1)
    if len(encoded) > MAX_MASK_BYTES:
        raise ValueError("Ground-truth mask exceeds byte limit")
    if hashlib.sha256(encoded).hexdigest() != sha256:
        raise ValueError("Ground-truth mask checksum mismatch")
    with Image.open(io.BytesIO(encoded)) as image:
        if image.size != size or image.width * image.height > MAX_MASK_PIXELS:
            raise ValueError("Ground-truth mask needs the bounded source pixel grid")
        if (
            image.format != "PNG"
            or image.mode not in {"1", "L"}
            or getattr(image, "n_frames", 1) != 1
        ):
            raise ValueError("Ground truth requires a single-frame binary PNG")
        pixels = np.asarray(image)
        if image.mode == "L" and np.any((pixels != 0) & (pixels != 255)):
            raise ValueError("Ground truth requires binary 0/255 pixels")
        return pixels.astype(np.bool_, copy=True)
