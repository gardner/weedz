"""The search windows of this ranking revision, stated so a device can reproduce them.

Parameters alone leave room for a different but plausible tiling (stepping at the maximum
stride and appending the edge, say), which would crop different pixels and so change
every score. So the manifest states the algorithm and carries conformance vectors: the
server's exact boxes for representative photo sizes. A device implementation must
reproduce every one before it is used.
"""

from typing import Any

from weedz.discovery import inference
from weedz.discovery.inference import RANKING_REVISION, region_boxes

ALGORITHM = (
    "Boxes are [x1, y1, x2, y2] in pixels, whole frame first: [0, 0, width, height]. "
    "Then square tiles of side round(min(width, height) * tile_percent_of_short_side / 100) "
    "(at least 1). Along each axis of length L, tile positions are [0] if L <= side; "
    "otherwise count = ceil((L - side) / (side * max_stride_percent_of_tile / 100)) + 1 "
    "positions round(i * (L - side) / (count - 1)) for i in 0..count-1, evenly spaced from "
    "0 to the far edge. If x positions times y positions exceed max_tiles, the long axis "
    "(x when width >= height) is thinned to max_tiles // (other axis's count) positions: "
    "step = (n - 1) / max(1, keep - 1), keeping sorted unique positions[round(i * step)]. "
    "Tiles are ordered row by row (y outer, x inner); a box equal to an earlier one is "
    "dropped. Round half to even. Each box is cropped, letterboxed to a square with "
    "letterbox_rgb, then pre-processed. A tile whose greyscale standard deviation is below "
    "featureless_greyscale_std_below cannot be a species' winning window; the whole frame "
    "is never excluded."
)
# Phone landscape and portrait, a square crop, a small photo, and a panorama whose long
# axis is thinned.
EXAMPLE_SIZES = [(4032, 3024), (3024, 4032), (1080, 1080), (640, 480), (9000, 1000)]


def _whole(value: float) -> int:
    """`value` as an integer, refusing one that is not whole (beyond float noise:
    0.6 * 100 is 60.00000000000001)."""
    if abs(value - round(value)) > 1e-9:
        raise ValueError(f"{value} is not a whole number; declare it in finer units")
    return round(value)


def windows() -> dict[str, Any]:
    """The window construction of this ranking revision, with its conformance vectors."""
    return {
        "ranking_revision": RANKING_REVISION,
        "algorithm": ALGORITHM,
        "tile_percent_of_short_side": _whole(inference.TILE_FRACTION * 100),
        "max_stride_percent_of_tile": _whole(inference.MAX_STRIDE * 100),
        "max_tiles": inference.MAX_TILES,
        "letterbox_rgb": list(inference.LETTERBOX),
        "featureless_greyscale_std_below": _whole(inference.FEATURELESS_STD),
        "examples": [
            {
                "width": width,
                "height": height,
                "boxes": [list(box) for box in region_boxes(width, height)],
            }
            for width, height in EXAMPLE_SIZES
        ],
    }
