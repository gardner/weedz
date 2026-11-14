"""A versioned, source-independent sample and annotation contract.

A sample says what evidence it carries and which tasks that evidence supports. Unknowns
stay `None` or `"unknown"`; validation refuses tasks the evidence cannot support rather
than silently weakening labels (an image label never becomes a mask).
"""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    model_validator,
)

SCHEMA_VERSION = 1

Supervision = Literal[
    "surveyed_point", "image_class", "box", "dense_mask", "sparse_mask", "occurrence", "unlabelled"
]
Task = Literal[
    "point_classification",
    "image_classification",
    "detection",
    "segmentation",
    "sparse_segmentation",
    "area_measurement",
    "site_selection",
    "inference",
]
# The supervision that can train or score each task. Inference needs none.
TASK_SUPERVISION: dict[str, frozenset[str]] = {
    "point_classification": frozenset({"surveyed_point"}),
    "image_classification": frozenset({"image_class"}),
    "detection": frozenset({"box"}),
    "segmentation": frozenset({"dense_mask"}),
    "sparse_segmentation": frozenset({"sparse_mask"}),
    "area_measurement": frozenset({"dense_mask"}),
    "site_selection": frozenset({"occurrence"}),
    "inference": frozenset(),
}
Review = Literal["unreviewed", "accepted", "rejected", "uncertain"]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
# A source names the namespace of "<source>:<source_id>", so it cannot hold the colon.
SourceName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]*$")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
Pixels = Annotated[float, Field(ge=0)]


class Contract(BaseModel):
    # JSON cannot hold NaN or infinity, so a manifest could not round-trip them.
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Rights(Contract):
    """Image and metadata licences are separate; `license_source` is where they were read."""

    media_license: Text
    metadata_license: Text
    creator: Text
    attribution: Text
    license_source: Text


class Media(Contract):
    uri: Text
    sha256: Sha256 | None = None
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    format: str | None = None


class Geography(Contract):
    """A WGS84 location as the source gave it: never a plant boundary or ground footprint."""

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    uncertainty_m: float | None = Field(default=None, ge=0)
    privacy: Literal["public", "obscured"] = "public"


class Ground(Contract):
    """Known ground sampling distance; without it no ground area can be measured."""

    gsd_m: float = Field(gt=0)


class Annotation(Contract):
    """One typed claim about a sample, with its origin and review state.

    Points are (x, y) and boxes (left, top, right, bottom) in original image pixels.
    """

    id: Text
    supervision: Supervision
    taxon: str | None = None
    label: Literal["present", "absent", "unknown", "ignored"] = "unknown"
    point: tuple[Pixels, Pixels] | None = None
    box: tuple[Pixels, Pixels, Pixels, Pixels] | None = None
    mask_uri: Text | None = None
    origin: Literal["source", "reviewer", "model"]
    review: Review = "unreviewed"
    reviewer: str | None = None
    recorded_at: str | None = None
    note: str = ""
    model: str | None = None
    score: float | None = None

    @model_validator(mode="after")
    def geometry_fits_supervision(self) -> "Annotation":
        kind = self.supervision
        if (self.box is not None) != (kind == "box"):
            raise ValueError(f"Only box supervision has a box, and it needs one, not {kind}")
        if self.box and not (self.box[0] < self.box[2] and self.box[1] < self.box[3]):
            raise ValueError("A box needs left < right and top < bottom")
        if (self.mask_uri is not None) != (kind in {"dense_mask", "sparse_mask"}):
            raise ValueError(f"Only mask supervision has a mask_uri, and it needs one, not {kind}")
        if (self.point is not None) != (kind == "surveyed_point"):
            raise ValueError(
                f"Only surveyed_point supervision has a point, and it needs one, not {kind}"
            )
        if kind == "unlabelled" and (self.taxon or self.label != "unknown"):
            raise ValueError("An unlabelled annotation names no taxon and no label")
        if self.origin == "model" and not self.model:
            raise ValueError("A model prediction names its model")
        return self

    def supervises(self) -> bool:
        """Evidence a task can rely on: a present or absent label, not a prediction, and not
        rejected on review. Unknown and ignored labels give a task no target."""
        return (
            self.label in {"present", "absent"}
            and self.origin != "model"
            and self.review != "rejected"
        )


class Sample(Contract):
    schema_version: Literal[1] = SCHEMA_VERSION
    # Namespaced "<source>:<source_id>" so IDs never collide across sources.
    id: Text
    source: SourceName
    source_id: Text
    # The source revision, query or run this sample was read from.
    snapshot: Text
    parent_id: str | None = None
    rights: Rights
    media: Media
    view: Literal["nadir", "oblique", "ground", "unknown"] = "unknown"
    scale: Literal["detail", "plant", "patch", "unknown"] = "unknown"
    geography: Geography | None = None
    ground: Ground | None = None
    captured_on: str | None = None
    groups: dict[str, str] = {}
    # The source's own label for the original subject: context, never supervision.
    original_label: str | None = None
    context: dict[str, str] = {}
    tasks: frozenset[Task]
    annotations: tuple[Annotation, ...] = ()

    @field_serializer("tasks")
    def sorted_tasks(self, tasks: frozenset[str]) -> list[str]:
        """Sorted, so a manifest's bytes and SHA-256 do not depend on the hash seed."""
        return sorted(tasks)

    @model_validator(mode="after")
    def supported(self) -> "Sample":
        if self.id != f"{self.source}:{self.source_id}":
            raise ValueError("A sample id is '<source>:<source_id>'")
        if len({note.id for note in self.annotations}) != len(self.annotations):
            raise ValueError("Annotation ids must be unique within a sample")
        for note in self.annotations:
            self._check_extent(note)
        for task in sorted(self.tasks):
            if reason := self._unsupported(task):
                raise ValueError(reason)
        return self

    def _check_extent(self, note: Annotation) -> None:
        width, height = self.media.width, self.media.height
        corners = [note.point] if note.point else []
        if note.box:
            corners += [note.box[:2], note.box[2:]]
        for x, y in corners:
            if (width and x > width) or (height and y > height):
                raise ValueError(f"Annotation {note.id} must lie inside the image")
        if note.supervision == "occurrence" and self.geography is None:
            raise ValueError("Occurrence supervision needs a real location")

    def _unsupported(self, task: str) -> str | None:
        needed = TASK_SUPERVISION[task]
        evidence = {note.supervision for note in self.annotations if note.supervises()}
        if needed and not needed & evidence:
            return f"{task} needs {' or '.join(sorted(needed))} supervision"
        if task == "area_measurement" and self.ground is None:
            return "area_measurement needs known ground geometry"
        return None


class UnsupportedTask(ValueError):
    pass


def require_task(sample: Sample, task: Task) -> Sample:
    """Refuse a sample for a task its adapter did not declare."""
    if task not in sample.tasks:
        raise UnsupportedTask(f"{sample.id} does not support {task}")
    return sample
