"""Decode published Region masks without constructing classifier crops or running models."""

import base64
import hashlib
import io
from typing import Literal

import numpy as np
from numpy.typing import NDArray
from PIL import Image


def proposal_mask(
    record: dict, *, size: tuple[int, int], kind: Literal["sam2", "sam3"]
) -> NDArray[np.bool_]:
    if kind not in {"sam2", "sam3"} or min(size) <= 0 or size[0] * size[1] > 40_000_000:
        raise ValueError("Unknown proposal kind or excessive source geometry")
    encoded = record["mask_png"]
    if not isinstance(encoded, str) or len(encoded) > 1_000_000:
        raise ValueError("Proposal mask exceeds retained-mask cap")
    with Image.open(io.BytesIO(base64.b64decode(encoded, validate=True))) as image:
        if (
            image.format != "PNG"
            or image.mode != "RGBA"
            or max(image.size) > 1024
            or getattr(image, "n_frames", 1) != 1
        ):
            raise ValueError("Unsupported proposal mask encoding or geometry")
        if list(image.size) != record["mask_size"]:
            raise ValueError("Proposal mask grid differs from its record")
        if abs(image.width * size[1] - image.height * size[0]) > max(size):
            raise ValueError("Proposal mask has a different source aspect ratio")
        pixels = np.asarray(image.getchannel("A")) > 0
    _identity(record, pixels, kind)
    with Image.fromarray(pixels) as mask:
        return np.asarray(mask.resize(size, Image.Resampling.NEAREST)).astype(np.bool_, copy=True)


def _identity(record: dict, pixels: NDArray[np.bool_], kind: str) -> None:
    prefix = b""
    if kind == "sam3":
        prompt = record.get("prompt")
        if not isinstance(prompt, str) or not 1 <= len(prompt) <= 80:
            raise ValueError("SAM3 mask needs its recorded bounded prompt")
        prefix = prompt.encode("utf-8") + b"\0"
    if not pixels.any() or hashlib.sha256(prefix + pixels.tobytes()).hexdigest() != record["id"]:
        raise ValueError("Proposal mask identity differs from retained pixels")
