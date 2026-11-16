"""Typed frozen release records and split rules; re-exported from weedz.release."""

import hashlib
import json
import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal

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

from weedz.contract import Sha256, SourceName, Task, Text
from weedz.gold import ReviewPolicy
from weedz.rights_profiles import RightsProfile

SplitName = Literal["fit", "validation", "test"]
TestStatus = Literal["fresh", "inspected", "used_for_selection"]
STATUS_ORDER: tuple[TestStatus, ...] = ("fresh", "inspected", "used_for_selection")
MANIFEST = "samples.jsonl"
RELEASE = "release.json"
ReleaseName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._-]*$")]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class HashSplit(Frozen):
    """Each group goes to a split by a stable SHA-256 of `seed:group`."""

    kind: Literal["hash"] = "hash"
    group_key: Text
    seed: Text
    fractions: dict[SplitName, Annotated[float, Field(ge=0)]]

    @model_validator(mode="after")
    def fractions_cover_one(self) -> "HashSplit":
        if not math.isclose(sum(self.fractions.values()), 1):
            raise ValueError("Split fractions must sum to 1")
        return self

    def assign(self, group: str) -> SplitName:
        digest = hashlib.sha256(f"{self.seed}:{group}".encode()).digest()
        position = int.from_bytes(digest[:8]) / 2**64
        cumulative = 0.0
        for name in ("fit", "validation", "test"):
            cumulative += self.fractions.get(name, 0)
            if position < cumulative:
                return name
        return "test"  # floating-point remainder at the very top of the range


class ExplicitSplit(Frozen):
    """Each group value is assigned by name; an unassigned group is refused, not guessed."""

    kind: Literal["explicit"] = "explicit"
    group_key: Text
    assignment: dict[str, SplitName]

    def assign(self, group: str) -> SplitName:
        if group not in self.assignment:
            raise ValueError(f"The split rule has no split for {self.group_key} {group!r}")
        return self.assignment[group]


SplitRule = Annotated[HashSplit | ExplicitSplit, Field(discriminator="kind")]


class ReleaseSpec(Frozen):
    """What a release is for and how it is split. `separate` names further group keys
    (e.g. a duplicate or encounter group) that must never span splits."""

    name: ReleaseName
    task: Task
    protocol: Text
    split: SplitRule
    separate: tuple[Text, ...] = ()
    buffer_m: Annotated[float, Field(ge=0)] | None = None
    test_status: TestStatus = "fresh"
    review_policy: ReviewPolicy | None = None
    rights_profile: RightsProfile | None = None

    @model_serializer(mode="wrap")
    def without_absent_policy(self, handler: SerializerFunctionWrapHandler) -> dict:
        data = handler(self)
        for key in ("review_policy", "rights_profile"):
            if data.get(key) is None:
                data.pop(key, None)
        return data

    @model_validator(mode="after")
    def explicit_gold_purpose(self) -> "ReleaseSpec":
        if self.review_policy is not None:
            if self.task != "detection":
                raise ValueError(
                    "The accepted gold review policy currently supports detection only"
                )
            if self.rights_profile is None:
                raise ValueError("A gold release needs an explicit rights profile")
        return self


class Members(Frozen):
    samples: list[str]
    groups: list[str]


class Counts(Frozen):
    """Samples and groups, and the labels, review states and taxa of their supervision."""

    samples: int
    groups: int
    labels: dict[str, int]
    reviews: dict[str, int]
    taxa: dict[str, int]
    categories: dict[str, int] = Field(default_factory=dict)
    checked_negatives: dict[str, int] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def without_absent_categories(self, handler: SerializerFunctionWrapHandler) -> dict:
        data = handler(self)
        for key in ("categories", "checked_negatives"):
            if not data.get(key):
                data.pop(key, None)
        return data


class Buffer(Frozen):
    distance_m: float
    basis: str
    # Samples without a usable location could not be checked against other splits.
    unbuffered: list[str]


class StatusChange(Frozen):
    status: TestStatus
    recorded_at: Text
    note: str = ""


class Release(Frozen):
    release_format: Literal[1, 2] = 1
    id: str
    name: ReleaseName
    task: Task
    protocol: Text
    split: SplitRule
    separate: list[str]
    contract_schema_version: int
    # Always the sibling file, so an edited record cannot point outside the release.
    manifest: Literal["samples.jsonl"] = MANIFEST
    manifest_sha256: Sha256
    source_snapshots: dict[SourceName, list[str]]
    licenses: list[str]
    buffer: Buffer | None
    splits: dict[SplitName, Members]
    excluded: dict[str, str]
    counts: dict[SplitName, Counts]
    test_status: TestStatus
    test_history: list[StatusChange] = Field(min_length=1)
    review_policy: ReviewPolicy | None = None
    rights_profile: RightsProfile | None = None
    metadata_licenses: list[str] | None = None
    assets: Mapping[Text, Sha256] | None = None

    @field_validator("assets")
    @classmethod
    def readonly_assets(cls, value: Mapping[str, str] | None) -> Mapping[str, str] | None:
        return MappingProxyType(dict(value)) if value is not None else None

    @field_serializer("assets")
    def sorted_assets(self, value: Mapping[str, str] | None) -> dict[str, str] | None:
        return dict(sorted(value.items())) if value is not None else None

    @model_serializer(mode="wrap")
    def without_absent_policy(self, handler: SerializerFunctionWrapHandler) -> dict:
        data = handler(self)
        for key in ("review_policy", "rights_profile", "metadata_licenses", "assets"):
            if data.get(key) is None:
                data.pop(key, None)
        return data

    @model_validator(mode="after")
    def history_only_advances(self) -> "Release":
        if self.contract_schema_version not in {1, 2}:
            raise ValueError("Unsupported release contract schema version")
        extensions = (
            self.contract_schema_version > 1,
            self.review_policy is not None,
            self.rights_profile is not None,
            self.metadata_licenses is not None,
            self.assets is not None,
            any(c.categories or c.checked_negatives for c in self.counts.values()),
        )
        if self.release_format == 1 and any(extensions):
            raise ValueError("Release format 1 cannot contain version 2 extensions")
        for before, after in zip(self.test_history, self.test_history[1:], strict=False):
            _check_advance(before.status, after.status)
        if self.test_history[-1].status != self.test_status:
            raise ValueError("test_status must be the latest test_history entry")
        return self

    def content_id(self) -> str:
        """The id implied by the frozen content. Later test status changes do not alter it,
        but the status at creation does, so an edit cannot restart the history as fresh.
        (Dropping later entries can only be detected against an outside copy of the record.)"""
        content = self.model_dump(mode="json", exclude={"id", "test_status", "test_history"})
        content["created_test_status"] = self.test_history[0].status
        canonical = json.dumps(content, sort_keys=True, separators=(",", ":"))
        return f"{self.name}-{hashlib.sha256(canonical.encode()).hexdigest()[:12]}"


def _check_advance(current: TestStatus, new: TestStatus) -> None:
    if STATUS_ORDER.index(new) < STATUS_ORDER.index(current):
        raise ValueError(f"A test status cannot return from {current} to {new}")
