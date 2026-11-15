"""Bounded masks and transforms in the EXIF-upright original coordinate frame."""

import hashlib
import io
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

REVISION = 1
MAX_SOURCE_PIXELS = 40_000_000


@dataclass(frozen=True)
class ProposalConfig:
    max_side: int = 768
    points_per_side: int = 8
    points_per_batch: int = 8
    max_proposals: int = 12
    min_area: int = 16
    context_fraction: float = 0.25

    def __post_init__(self) -> None:
        if not (64 <= self.max_side <= 1024 and 1 <= self.max_proposals <= 24):
            raise ValueError("Resolution/proposal cap exceeded")
        if not (1 <= self.points_per_side <= 16 and 1 <= self.points_per_batch <= 16):
            raise ValueError("Point budget exceeded")
        if self.min_area < 1 or not 0 <= self.context_fraction <= 1:
            raise ValueError("Invalid area/context policy")


def cache_key(image: bytes, checkpoint: str, config: ProposalConfig) -> str:
    stamp = json.dumps([REVISION, checkpoint, asdict(config)], sort_keys=True)
    return hashlib.sha256(image + stamp.encode()).hexdigest()


def upright(path: Path) -> Image.Image:
    if path.stat().st_size > 20_000_000:
        raise ValueError("Source exceeds 20 MB experiment limit")
    with Image.open(path) as source:
        if source.width * source.height > MAX_SOURCE_PIXELS:
            raise ValueError("Source exceeds 40 megapixel experiment limit")
        return ImageOps.exif_transpose(source).convert("RGB")


@dataclass
class Region:
    mask: np.ndarray
    box: tuple[int, int, int, int]
    context_box: tuple[int, int, int, int]
    quality: dict[str, float]
    views: dict[str, Image.Image]

    def record(self) -> dict[str, Any]:
        """PNG is an original-aligned low-resolution mask, never an identification."""
        import base64

        rgba = np.zeros((*self.mask.shape, 4), dtype=np.uint8)
        rgba[self.mask] = (80, 255, 100, 125)
        output = io.BytesIO()
        Image.fromarray(rgba).save(output, format="PNG")
        return {
            "id": hashlib.sha256(self.mask.tobytes()).hexdigest(),
            "box": list(self.box),
            "context_box": list(self.context_box),
            "mask_size": [self.mask.shape[1], self.mask.shape[0]],
            "mask_png": base64.b64encode(output.getvalue()).decode(),
            "mask_quality": self.quality,
            "view_transforms": {
                name: {
                    "source_box": list(self.context_box if name == "context" else self.box),
                    "resized_size": list(view.size),
                    "resize": "LANCZOS",
                    "padding": "centred neutral square before BioCLIP transform",
                }
                for name, view in self.views.items()
            },
        }


def _region(image: Image.Image, mask: np.ndarray, raw: dict, config: ProposalConfig) -> Region:
    full = Image.fromarray(mask).resize(image.size, Image.Resampling.NEAREST)
    box = full.getbbox()
    assert box is not None
    x1, y1, x2, y2 = box
    pad = round(max(x2 - x1, y2 - y1) * config.context_fraction)
    context = (
        max(0, x1 - pad),
        max(0, y1 - pad),
        min(image.width, x2 + pad),
        min(image.height, y2 + pad),
    )
    tight, surrounding = image.crop(box), image.crop(context)
    for view in (tight, surrounding):
        view.thumbnail((config.max_side, config.max_side), Image.Resampling.LANCZOS)
    visible = full.crop(box).resize(tight.size, Image.Resampling.NEAREST).convert("L")
    neutral = Image.new("RGB", tight.size, (124, 116, 104))
    neutral.paste(tight, mask=visible.point(lambda p: 255 if p else 0))
    return Region(
        mask,
        box,
        context,
        {key: float(raw[key]) for key in ("predicted_iou", "stability_score")},
        {"tight": tight, "masked": neutral, "context": surrounding},
    )


def proposals(image: Image.Image, raw: list[dict], config: ProposalConfig) -> list[Region]:
    """Keep nested/overlapping masks; remove only exact duplicates and tiny/empty masks."""
    result, seen = [], set()
    ordered = sorted(raw, key=lambda row: float(row["predicted_iou"]), reverse=True)
    for row in ordered:
        mask = np.asarray(row["segmentation"], dtype=bool)
        if mask.ndim != 2 or max(mask.shape) > config.max_side:
            raise ValueError("Mask exceeds configured geometry")
        if abs(mask.shape[1] / mask.shape[0] - image.width / image.height) > 2 / min(mask.shape):
            raise ValueError("Mask and upright original have different aspect ratios")
        signature = hashlib.sha256(mask.tobytes()).digest()
        if int(mask.sum()) < config.min_area or signature in seen:
            continue
        seen.add(signature)
        result.append(_region(image, mask, row, config))
        if len(result) == config.max_proposals:
            break
    return result
