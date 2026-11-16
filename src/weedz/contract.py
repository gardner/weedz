"""A versioned, source-independent sample and annotation contract.

A sample says what evidence it carries and which tasks that evidence supports. Unknowns
stay `None` or `"unknown"`; validation refuses tasks the evidence cannot support rather
than silently weakening labels (an image label never becomes a mask).
"""

import json
from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StringConstraints,
    field_serializer,
    field_validator,
    model_serializer,
    model_validator,
)

from weedz.consent import Permission
from weedz.contract_versions import (
    LEGACY_SCHEMA_VERSION,
    materialize_sample_fields,
    required_sample_version,
    sample_version_fields,
)
from weedz.contract_versions import (
    SCHEMA_VERSION as SCHEMA_VERSION,
)
from weedz.review_values import FrozenJson, freeze_json, thaw_json

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


class ContributorConsent(Contract):
    """What a contributor permitted for their own photo, under which consent wording (#60)."""

    version: Text
    uses: frozenset[Permission]
    # When the contributor withdrew it; from then on the photo serves no further use.
    withdrawn_at: Text | None = None

    @field_serializer("uses")
    def sorted_uses(self, uses: frozenset[str]) -> list[str]:
        return sorted(uses)


class Rights(Contract):
    """Image and metadata licences are separate; `license_source` is where they were read."""

    media_license: Text
    metadata_license: Text
    # None when the source gives only an attribution string, which then stays the
    # authoritative credit; a creator is never guessed from, e.g., the observer account.
    creator: Text | None = None
    attribution: Text
    license_source: Text
    # Only for a photo its contributor sent us directly; sourced material has none and is
    # governed by its licence alone.
    consent: ContributorConsent | None = None

    @model_serializer(mode="wrap")
    def without_absent_consent(self, handler: SerializerFunctionWrapHandler) -> dict:
        """Rights without consent serialise as before, so existing manifests keep their bytes."""
        data = handler(self)
        if data.get("consent", True) is None:
            del data["consent"]
        return data


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


class ReviewEvidence(Contract):
    """Source claims and human reviews keep their actual provenance and media identity."""

    media_sha256: Sha256
    origin: Literal["source", "reviewer"]
    recorded_at: Text | None = None
    evidence: Mapping[Text, Text] = Field(default_factory=dict, validate_default=True)

    @field_validator("evidence")
    @classmethod
    def readonly_evidence(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        return MappingProxyType(dict(value))

    @field_serializer("evidence")
    def sorted_evidence(self, evidence: Mapping[str, str]) -> dict[str, str]:
        return dict(sorted(evidence.items()))

    @model_validator(mode="after")
    def timestamp_is_attributed(self) -> "ReviewEvidence":
        if self.recorded_at is None:
            if self.origin == "reviewer":
                raise ValueError("A human review needs its actual recorded_at timestamp")
            return self
        try:
            value = datetime.fromisoformat(self.recorded_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("recorded_at needs an ISO timestamp with timezone") from error
        if value.utcoffset() is None:
            raise ValueError("recorded_at needs an ISO timestamp with timezone")
        return self


class Completeness(ReviewEvidence):
    """Coverage of named targets, never a negative inferred from missing annotations.

    An exhaustive upstream annotation protocol is source evidence, not our own accepted
    human judgement. Gold policies impose their stricter review requirements separately.
    """

    id: Text
    task: Literal["detection", "segmentation"]
    scope: Literal["whole_image"] = "whole_image"
    taxa: tuple[Text, ...] = ()
    categories: tuple[Text, ...] = ()
    status: Literal["exhaustive", "partial", "unknown"]
    author: Text | None = None
    review: Review = "unreviewed"
    reviewers: tuple[Text, ...] = ()

    @field_validator("taxa", "categories")
    @classmethod
    def unique_scope(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("Completeness scope cannot repeat a target")
        return tuple(sorted(values))

    @model_validator(mode="after")
    def explicit_scope(self) -> "Completeness":
        if not self.taxa and not self.categories:
            raise ValueError("Completeness needs named taxa or source categories")
        if self.origin == "reviewer" and self.author is None:
            raise ValueError("Reviewer completeness needs its author")
        return self

    def supervises(self) -> bool:
        if self.status != "exhaustive" or self.review in {"rejected", "uncertain"}:
            return False
        if self.origin == "source":
            return bool(self.evidence)
        return self.review == "accepted" and bool(self.reviewers)

    def targets(self, note: "Annotation") -> set[tuple[str, str]]:
        """Keep functional categories separate from taxa when comparing target scopes."""
        return {
            (kind, value)
            for kind, value, scope in (
                ("taxon", note.taxon, self.taxa),
                ("category", note.category, self.categories),
            )
            if value is not None and value in scope
        }


class ReviewEvent(ReviewEvidence):
    """An immutable source event or human revision, with evidence snapshots addressed by hash."""

    id: Text
    sample_id: Text
    actor: Text
    action: Text
    dimension: Text
    annotation_id: Text | None = None
    supersedes: Text | None = None
    payload: Mapping[str, FrozenJson] = Field(default_factory=dict, validate_default=True)

    @field_validator("payload", mode="before")
    @classmethod
    def json_values_only(cls, value: object) -> object:
        # Reject non-JSON Python objects before scalar coercion, while accepting
        # the readonly mapping/tuple representation of an already validated record.
        return freeze_json(value)

    @field_validator("payload")
    @classmethod
    def finite_json(cls, value: Mapping[str, FrozenJson]) -> Mapping[str, FrozenJson]:
        frozen = {key: freeze_json(item) for key, item in value.items()}
        json.dumps({key: thaw_json(item) for key, item in frozen.items()}, allow_nan=False)
        return MappingProxyType(frozen)

    @field_serializer("payload")
    def json_payload(self, value: Mapping[str, FrozenJson]) -> dict:
        return {key: thaw_json(value[key]) for key in sorted(value)}


class Annotation(Contract):
    """One typed claim about a sample, with its origin and review state.

    Points are (x, y) and boxes (left, top, right, bottom) in original image pixels.
    """

    id: Text
    supervision: Supervision
    taxon: Text | None = None
    # A publisher's functional class (e.g. crop/weed) is not a scientific taxon.
    category: Text | None = None
    label: Literal["present", "absent", "unknown", "ignored"] = "unknown"
    point: tuple[Pixels, Pixels] | None = None
    box: tuple[Pixels, Pixels, Pixels, Pixels] | None = None
    mask_uri: Text | None = None
    mask_sha256: Sha256 | None = None
    origin: Literal["source", "reviewer", "model"]
    review: Review = "unreviewed"
    # Who made the claim (for reviewer-origin annotations), and who reviewed it: different
    # people, e.g. one reviewer records a plant and others judge its identity.
    author: str | None = None
    # A collection, never a joined string: a name may itself contain any separator.
    reviewers: tuple[Text, ...] = ()
    recorded_at: str | None = None
    note: str = ""
    model: Text | None = None
    score: float | None = None

    @model_serializer(mode="wrap")
    def without_absent_extensions(self, handler: SerializerFunctionWrapHandler) -> dict:
        data = handler(self)
        for key in ("category", "mask_sha256"):
            if data.get(key) is None:
                data.pop(key, None)
        return data

    @model_validator(mode="after")
    def geometry_fits_supervision(self) -> "Annotation":
        kind = self.supervision
        if (self.box is not None) != (kind == "box"):
            raise ValueError(f"Only box supervision has a box, and it needs one, not {kind}")
        if self.box and not (self.box[0] < self.box[2] and self.box[1] < self.box[3]):
            raise ValueError("A box needs left < right and top < bottom")
        if (self.mask_uri is not None) != (kind in {"dense_mask", "sparse_mask"}):
            raise ValueError(f"Only mask supervision has a mask_uri, and it needs one, not {kind}")
        if self.mask_sha256 is not None and self.mask_uri is None:
            raise ValueError("A mask_sha256 needs mask supervision and a mask_uri")
        if (self.point is not None) != (kind == "surveyed_point"):
            raise ValueError(
                f"Only surveyed_point supervision has a point, and it needs one, not {kind}"
            )
        if self.origin == "model" and not self.model:
            raise ValueError("A model prediction names its model")
        if self.origin == "reviewer" and not (self.author or "").strip():
            raise ValueError("A reviewer annotation names its author")
        return self

    @model_validator(mode="after")
    def label_names_its_taxon(self) -> "Annotation":
        if self.supervision == "unlabelled" and (
            self.taxon or self.category or self.label != "unknown"
        ):
            raise ValueError("An unlabelled annotation names no taxon and no label")
        if self.label in {"present", "absent"} and not (self.taxon or self.category):
            raise ValueError("A present or absent label names its taxon or source category")
        return self

    def supervises(self) -> bool:
        """Evidence a task can rely on: a present or absent label, not a prediction, and not
        rejected or left uncertain (including disputed) on review. Unknown and ignored labels
        give a task no target."""
        return (
            self.label in {"present", "absent"}
            and self.origin != "model"
            and self.review not in {"rejected", "uncertain"}
        )


class Sample(Contract):
    schema_version: Literal[1, 2] = LEGACY_SCHEMA_VERSION

    @model_validator(mode="before")
    @classmethod
    def declared_version(cls, data: object) -> object:
        return sample_version_fields(data)

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
    completeness: tuple[Completeness, ...] = ()
    review_history: tuple[ReviewEvent, ...] = ()

    @model_serializer(mode="wrap")
    def without_absent_extensions(self, handler: SerializerFunctionWrapHandler) -> dict:
        data = handler(self)
        for key in ("completeness", "review_history"):
            if not data.get(key):
                data.pop(key, None)
        return data

    @field_serializer("groups", "context")
    def sorted_mapping(self, mapping: dict[str, str]) -> dict[str, str]:
        """Sorted, so a manifest's bytes do not depend on how a source built the mapping."""
        return dict(sorted(mapping.items()))

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
        self._check_review_evidence()
        for task in sorted(self.tasks):
            if reason := self._unsupported(task):
                raise ValueError(reason)
        return self

    def _check_review_evidence(self) -> None:
        if len({item.id for item in self.completeness}) != len(self.completeness):
            raise ValueError("Completeness ids must be unique within a sample")
        for coverage in self.completeness:
            if coverage.media_sha256 != self.media.sha256:
                raise ValueError("Completeness media SHA differs from the sample")
            self._check_complete_geometry(coverage)
        self._check_history()

    def _check_complete_geometry(self, coverage: Completeness) -> None:
        if not coverage.supervises():
            return
        required: set[tuple[str, str]] = set()
        represented: set[tuple[str, str]] = set()
        for note in self.annotations:
            if note.label != "present" or not note.supervises():
                continue
            targets = coverage.targets(note)
            required.update(targets)
            if note.supervision in TASK_SUPERVISION[coverage.task]:
                represented.update(targets)
        if not required <= represented:
            raise ValueError("Completeness contradicts known positive labels missing task geometry")

    def _check_history(self) -> None:
        seen: set[str] = set()
        for event in self.review_history:
            if event.id in seen or event.sample_id != self.id:
                raise ValueError("Review history needs unique events for this sample")
            if event.media_sha256 != self.media.sha256:
                raise ValueError("Review history media SHA differs from the sample")
            if event.supersedes is not None and event.supersedes not in seen:
                raise ValueError("Review history supersedes an unknown or later revision")
            seen.add(event.id)

    def _check_extent(self, note: Annotation) -> None:
        width, height = self.media.width or float("inf"), self.media.height or float("inf")
        # A point addresses a pixel in the half-open extent; a box's far edges may touch it.
        inside_point = not note.point or (note.point[0] < width and note.point[1] < height)
        inside_box = not note.box or (note.box[2] <= width and note.box[3] <= height)
        if not (inside_point and inside_box):
            raise ValueError(f"Annotation {note.id} must lie inside the image")
        if note.supervision == "occurrence" and self.geography is None:
            raise ValueError("Occurrence supervision needs a real location")

    def _unsupported(self, task: str) -> str | None:
        needed = TASK_SUPERVISION[task]
        evidence = {note.supervision for note in self.annotations if note.supervises()}
        if any(item.task == task and item.supervises() for item in self.completeness):
            return None
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


def revise_sample(sample: Sample, **updates: Any) -> Sample:
    """Validate a revision and explicitly upgrade its wire version, never downgrade it."""
    fields = sample.model_dump(mode="python")
    fields.update(updates)
    fields = materialize_sample_fields(fields)
    minimum = max(sample.schema_version, required_sample_version(fields))
    requested = updates.get("schema_version", minimum)
    if type(requested) is not int or requested < minimum:
        raise ValueError("A sample revision cannot lower its required schema version")
    fields["schema_version"] = requested
    return Sample.model_validate(fields)
