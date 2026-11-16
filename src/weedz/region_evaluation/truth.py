"""Keep source geometry and task granularity intact when constructing denominators."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from weedz.contract import Annotation
from weedz.region_evaluation.geometry import Box, box_iou

type TruthOrigin = Literal["source", "reviewer"]


@dataclass(frozen=True)
class LabelledBox:
    id: str
    box: Box
    taxon: str | None
    category: str | None
    origin: str
    review: str


def eligible_positive(annotation: Annotation, *, origin: TruthOrigin | None = None) -> bool:
    """Source truth keeps its actual status; our reviewer drafts need acceptance."""
    return (
        annotation.label == "present"
        and (origin is None or annotation.origin == origin)
        and annotation.supervises()
        and (annotation.origin == "source" or annotation.review == "accepted")
    )


def labelled_boxes(
    annotations: Sequence[Annotation], *, size: tuple[int, int], origin: TruthOrigin = "source"
) -> tuple[LabelledBox, ...]:
    """Select original box annotations; do not invent boxes from image or mask labels."""
    if min(size) <= 0:
        raise ValueError("Need positive source frame dimensions")
    if len({annotation.id for annotation in annotations}) != len(annotations):
        raise ValueError("Duplicate annotation identities")
    boxes: list[LabelledBox] = []
    for annotation in annotations:
        if not eligible_positive(annotation, origin=origin) or annotation.box is None:
            continue
        box = annotation.box
        box_iou(box, box)
        if box[2] > size[0] or box[3] > size[1]:
            raise ValueError("Ground-truth box escapes source frame")
        boxes.append(
            LabelledBox(
                annotation.id,
                box,
                annotation.taxon,
                annotation.category,
                annotation.origin,
                annotation.review,
            )
        )
    return tuple(boxes)
