"""Source-coordinate geometry for tiled plant proposals and complete crop views."""

import math

import numpy as np
from PIL import Image

Box = tuple[int, int, int, int]
Size = tuple[int, int]


def _size(size: Size) -> None:
    if len(size) != 2 or any(type(value) is not int or value < 1 for value in size):
        raise ValueError("Use positive integer image dimensions")


def plant_windows(size: Size) -> list[Box]:
    """Whole image plus four corner windows with nominal 20% overlap per tile."""
    _size(size)
    width, height = size
    span_x, span_y = math.ceil(width / 1.8), math.ceil(height / 1.8)
    windows = [(0, 0, width, height)]
    windows.extend(
        (x, y, x + span_x, y + span_y) for y in (0, height - span_y) for x in (0, width - span_x)
    )
    return list(dict.fromkeys(windows))


def source_mask(mask: np.ndarray, window: Box) -> tuple[Box, np.ndarray]:
    """Nearest-resample one model mask to its source window, retaining a tight ROI."""
    left, top, right, bottom = window
    if min(left, top) < 0 or right <= left or bottom <= top:
        raise ValueError("Invalid source window")
    if mask.dtype != bool or mask.ndim != 2 or min(mask.shape) < 1 or not mask.any():
        raise ValueError("Use a nonempty two-dimensional boolean model mask")
    source = Image.fromarray(mask).resize((right - left, bottom - top), Image.Resampling.NEAREST)
    box = source.getbbox()
    if box is None:
        raise ValueError("Mask vanished on the original source grid")
    x1, y1, x2, y2 = box
    return (left + x1, top + y1, left + x2, top + y2), np.array(source.crop(box), dtype=bool)


def _nearest_coordinates(source_length: int, view_length: int) -> np.ndarray:
    """Match Pillow's affine NEAREST sampling using only preview-sized storage."""
    # Pillow first stores the source extent in a C float, then scales in double.
    step = float(np.float32(source_length)) / view_length
    position = step * 0.5
    coordinates = np.empty(view_length, dtype=np.int64)
    for index in range(view_length):
        coordinates[index] = int(position)
        # Incremental addition preserves Pillow's floating-point rounding ties.
        position += step
    return coordinates


def viewing_mask(mask: np.ndarray, box: Box, source_size: Size, view_size: Size) -> np.ndarray:
    """Project an ROI exactly as a full source canvas resized with nearest filtering."""
    _size(source_size)
    _size(view_size)
    left, top, right, bottom = box
    width, height = source_size
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError("Mask ROI is outside the source image")
    if mask.dtype != bool or mask.shape != (bottom - top, right - left):
        raise ValueError("Mask pixels disagree with the source ROI")
    xs = _nearest_coordinates(width, view_size[0])
    ys = _nearest_coordinates(height, view_size[1])
    columns = np.flatnonzero((xs >= left) & (xs < right))
    rows = np.flatnonzero((ys >= top) & (ys < bottom))
    result = np.zeros((view_size[1], view_size[0]), dtype=bool)
    result[np.ix_(rows, columns)] = mask[np.ix_(ys[rows] - top, xs[columns] - left)]
    return result


def whole_crop(image: Image.Image) -> Image.Image:
    """Bound memory and add enough square padding for the released 416→384 crop."""
    if image.mode != "RGB" or min(image.size) < 1:
        raise ValueError("Use a nonempty RGB crop")
    crop = image.copy()
    crop.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    side = math.ceil(max(crop.size) * 416 / 384) + 2
    padded = Image.new("RGB", (side, side), (128, 128, 128))
    padded.paste(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    return padded
