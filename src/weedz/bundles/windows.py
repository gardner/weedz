"""The search windows of this ranking revision, stated so a device can reproduce them.

Parameters alone leave room for a different but plausible tiling (stepping at the maximum
stride and appending the edge, say), which would crop different pixels and so change
every score. So the manifest states the algorithm and carries conformance vectors: the
server's exact boxes for representative photo sizes. A device implementation must
reproduce every one before it is used.
"""

from typing import Any

import numpy as np

from weedz.discovery import inference
from weedz.discovery.inference import RANKING_REVISION, region_boxes, summarize_scores
from weedz.discovery.records import SPECIES

ALGORITHM = (
    "Decode the photo, apply its EXIF orientation so it is upright, and convert it to RGB "
    "(8 bits per channel); width, height and every box refer to that upright image. "
    "Boxes are [x1, y1, x2, y2] in pixels, whole frame first: [0, 0, width, height]. "
    "Then square tiles of side round(min(width, height) * tile_percent_of_short_side / 100) "
    "(at least 1). Along each axis of length L, tile positions are [0] if L <= side; "
    "otherwise count = ceil((L - side) / (side * max_stride_percent_of_tile / 100)) + 1 "
    "positions round(i * (L - side) / (count - 1)) for i in 0..count-1, evenly spaced from "
    "0 to the far edge. If x positions times y positions exceed max_tiles, the long axis "
    "(x when width >= height) is thinned to max_tiles // (other axis's count) positions: "
    "step = (n - 1) / max(1, keep - 1), keeping sorted unique positions[round(i * step)]. "
    "Tiles are ordered row by row (y outer, x inner); a box equal to an earlier one is "
    "dropped. Round half to even. Each box is cropped and letterboxed to a square of side "
    "max(crop width, crop height) filled with letterbox_rgb, the crop pasted at "
    "((side - width) // 2, (side - height) // 2), so an odd extra pixel of padding goes to "
    "the right and bottom; then it is pre-processed. A tile is featureless when the "
    "population standard deviation (divide by N) of its greyscale pixels is below "
    "featureless_greyscale_std_below, greyscale being ITU-R 601-2 luma, L = R * 299/1000 + "
    "G * 587/1000 + B * 114/1000, computed exactly as PIL mode L does: "
    "(R * 19595 + G * 38470 + B * 7471 + 32768) >> 16; it is measured on the un-padded "
    "crop. A featureless tile cannot be a species' winning window; the whole frame is "
    "never excluded."
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


RULE = (
    "Score every window embedding against every text_table row (cosine similarity). The "
    "first target_count rows are watchlist targets, the rest comparison labels. For each "
    "target, a window's margin is its similarity to that target minus its highest "
    "similarity to any comparison label; the target's margin is the largest such margin "
    "over the eligible windows (the whole frame and every non-featureless tile), and the "
    "window giving it is the target's box (the first such window on a tie). The top "
    "suggestion is the target with the largest margin (the first in watchlist order on a "
    "tie). Examples use synthetic reduced tables with 3 target and 2 comparison columns, in "
    "integer units; margins are in the same units."
)
# Windows x (3 targets, 2 comparisons), in thousandths. The second puts the strongest
# target evidence in a featureless tile, which must not win.
SCORING_EXAMPLES: list[dict[str, Any]] = [
    {"similarities": [[210, 180, 150, 200, 190], [260, 170, 240, 220, 180]], "featureless": []},
    {
        "similarities": [
            [200, 230, 150, 210, 205],
            [320, 140, 150, 160, 150],
            [250, 150, 240, 200, 170],
        ],
        "featureless": [1],
    },
]


def scoring() -> dict[str, Any]:
    """How window similarities become margins and a top suggestion, with vectors."""
    examples = []
    for case in SCORING_EXAMPLES:
        scores = np.array(case["similarities"], dtype=float)
        eligible = [index not in case["featureless"] for index in range(len(scores))]
        boxes = [(0, 0, 1, 1)] * len(scores)
        result = summarize_scores(scores, boxes, list(SPECIES), len(SPECIES), eligible)
        examples.append(
            {
                "similarities": case["similarities"],
                "featureless_windows": case["featureless"],
                "margins": {row["name"]: round(row["margin"]) for row in result["species"]},
                "best_species": result["best_species"],
            }
        )
    return {"ranking_revision": RANKING_REVISION, "rule": RULE, "examples": examples}
