"""Decode supported human regions; masks and boxes remain distinct supervision."""

import io
import math
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class Region:
    id: str
    taxon: str
    box: tuple[float, float, float, float] | None = None
    mask: bytes | None = None


def _number(value: Any) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Region coordinates must be finite numbers")
    return float(value)


def _mask(value: dict, size: tuple[int, int]) -> bytes:
    from label_studio_sdk.converter.brush import decode_rle

    rle = value.get("rle")
    if (
        value.get("format") != "rle"
        or not isinstance(rle, list)
        or len(rle) < 4
        or len(rle) > 160_000_000
        or any(type(v) is not int or not 0 <= v <= 255 for v in rle)
    ):
        raise ValueError("Invalid brush RLE bytes")
    width, height = size
    # The official format starts with the decoded uint8 count. Check allocation
    # against source geometry before asking the maintained SDK to decode it.
    if int.from_bytes(bytes(rle[:4]), "big") != width * height * 4:
        raise ValueError("Brush RLE size differs from source geometry")
    try:
        rgba = decode_rle(rle).reshape((height, width, 4))
    except (ValueError, IndexError, OverflowError) as error:
        raise ValueError("Malformed brush RLE") from error
    alpha = rgba[:, :, 3]
    if not np.isin(alpha, [0, 255]).all() or not alpha.any():
        raise ValueError("Human mask must have nonempty binary foreground")
    out = io.BytesIO()
    Image.fromarray(alpha).save(out, format="PNG")
    return out.getvalue()


def region_geometry(row: dict, size: tuple[int, int], taxa: set[str]) -> tuple[str, str, str, dict]:
    width, height = size
    if not 0 < width * height <= 40_000_000:
        raise ValueError("Human region exceeds geometry cap")
    kind = row.get("type")
    if not isinstance(kind, str):
        raise ValueError("Region requires a supported type")
    control = {"rectanglelabels": "review_boxes", "brushlabels": "regions"}.get(kind)
    if (
        control is None
        or row.get("from_name") != control
        or row.get("to_name") != "image"
        or row.get("original_width") != width
        or row.get("original_height") != height
        or row.get("image_rotation") != 0
    ):
        raise ValueError("Unsupported control, rotation or original image geometry")
    identifier, value = row.get("id"), row.get("value")
    if not isinstance(identifier, str) or not identifier or not isinstance(value, dict):
        raise ValueError("Region needs an identity and value")
    labels = value.get(kind)
    if not isinstance(labels, list) or len(labels) != 1 or labels[0] not in taxa:
        raise ValueError("Region needs one declared taxon")
    if kind == "rectanglelabels":
        _rectangle(identifier, labels[0], value, size)
    return kind, identifier, labels[0], value


def decode_region(row: dict, size: tuple[int, int], taxa: set[str]) -> Region:
    kind, identifier, taxon, value = region_geometry(row, size, taxa)
    if kind == "brushlabels":
        return Region(identifier, taxon, mask=_mask(value, size))
    return _rectangle(identifier, taxon, value, size)


def _rectangle(identifier: str, taxon: str, value: dict, size: tuple[int, int]) -> Region:
    width, height = size
    if value.get("rotation") != 0:
        raise ValueError("Rotated rectangles are not supported")
    x, y, w, h = (_number(value.get(key)) for key in ("x", "y", "width", "height"))
    right, bottom = _percentage_end(x, w), _percentage_end(y, h)
    return Region(
        identifier,
        taxon,
        (
            x * width / 100,
            y * height / 100,
            min(width, right * width / 100),
            min(height, bottom * height / 100),
        ),
    )


def _percentage_end(start: float, extent: float) -> float:
    end = start + extent
    # Separately rounded export percentages can exceed the exact edge by a few ulps.
    if not (0 <= start < 100 and start < end <= 100 + 1e-9):
        raise ValueError("Rectangle must have positive area inside original image")
    return min(100, end)
