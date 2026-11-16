"""Frozen dataset releases: exact samples, whole-group splits and a protected test.

A release is a directory holding `samples.jsonl` (the contract manifest) and a small
`release.json`. Whole groups are assigned to splits before anything is derived from them;
a release whose groups or parents span splits, or whose splits lack task evidence, is
refused, as is one keeping a photo its contributor did not permit for training (#60).
Whether the test is still a fresh holdout is recorded and can only advance.
"""

import hashlib
import json
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StringConstraints,
    model_serializer,
    model_validator,
)

from weedz.consent import refusal
from weedz.contract import (
    TASK_SUPERVISION,
    Annotation,
    Sample,
    Sha256,
    SourceName,
    Task,
    Text,
    require_task,
)
from weedz.manifest import manifest_bytes, read_manifest, write_atomic, write_manifest

SplitName = Literal["fit", "validation", "test"]
# Protection order: the test is never trimmed, then validation, then fit.
SPLITS: tuple[SplitName, ...] = ("test", "validation", "fit")
TestStatus = Literal["fresh", "inspected", "used_for_selection"]
STATUS_ORDER: tuple[TestStatus, ...] = ("fresh", "inspected", "used_for_selection")
# Tasks whose evaluation needs both labels in every split.
BINARY_TASKS = frozenset({"point_classification"})
EARTH_RADIUS_M = 6_371_000
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

    @model_serializer(mode="wrap")
    def without_absent_categories(self, handler: SerializerFunctionWrapHandler) -> dict:
        data = handler(self)
        if not data.get("categories"):
            data.pop("categories", None)
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

    @model_validator(mode="after")
    def history_only_advances(self) -> "Release":
        if self.contract_schema_version not in {1, 2}:
            raise ValueError("Unsupported release contract schema version")
        if self.release_format == 1 and (
            self.contract_schema_version > 1
            or any(count.categories for count in self.counts.values())
        ):
            raise ValueError("Release format 1 cannot contain version 2 sample/category extensions")
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


def _assign(samples: list[Sample], spec: ReleaseSpec) -> dict[str, SplitName]:
    key = spec.split.group_key
    assigned: dict[str, SplitName] = {}
    for sample in samples:
        require_task(sample, spec.task)
        if key not in sample.groups:
            raise ValueError(f"{sample.id} has no {key!r} group")
        assigned[sample.id] = spec.split.assign(sample.groups[key])
    if len(assigned) != len(samples):
        raise ValueError("Duplicate sample ids in release")
    return assigned


def _locatable(sample: Sample) -> bool:
    # An obscured point is deliberately displaced, so distances to it mean nothing.
    return sample.geography is not None and sample.geography.privacy == "public"


def _within(sample: Sample, other: Sample, buffer_m: float) -> bool:
    a, b = sample.geography, other.geography
    assert a is not None and b is not None
    lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
    dlat, dlon = lat2 - lat1, math.radians(b.longitude - a.longitude)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    distance = 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))
    return distance <= buffer_m + (a.uncertainty_m or 0) + (b.uncertainty_m or 0)


def _buffer(
    samples: list[Sample], assigned: dict[str, SplitName], buffer_m: float
) -> tuple[Buffer, dict[str, str]]:
    """Exclude validation points near the test, then fit points near either."""
    located = [sample for sample in samples if _locatable(sample)]
    excluded: dict[str, str] = {}
    protected: list[Sample] = []
    for name in SPLITS:
        members = [sample for sample in located if assigned[sample.id] == name]
        for sample in members:
            near = next((o for o in protected if _within(sample, o, buffer_m)), None)
            if near is not None:
                excluded[sample.id] = f"within {buffer_m} m of {assigned[near.id]}"
        protected += [sample for sample in members if sample.id not in excluded]
    buffer = Buffer(
        distance_m=buffer_m,
        basis="great-circle distance between WGS84 points plus known coordinate "
        "uncertainty (unknown counts as zero); footprints unknown",
        unbuffered=sorted(sample.id for sample in samples if not _locatable(sample)),
    )
    return buffer, excluded


def _lineage_roots(samples: list[Sample]) -> dict[str, str]:
    """Each sample's earliest known ancestor (itself when it has none), so a parent, its
    derivatives and theirs all share one lineage group."""
    parents = {sample.id: sample.parent_id for sample in samples}
    roots: dict[str, str] = {}
    for sample in samples:
        current, visited = sample.id, {sample.id}
        while parent := parents.get(current):
            if parent in visited:
                raise ValueError(f"{sample.id} has a cyclic parent_id lineage")
            # An ancestor outside the release has no entry, which ends the walk there.
            current = parent
            visited.add(parent)
        roots[sample.id] = current
    return roots


def _check_separation(
    kept: list[Sample], assigned: dict[str, SplitName], keys: list[str], roots: dict[str, str]
) -> None:
    seen: dict[tuple[str, str], SplitName] = {}
    for sample in kept:
        labelled = [(key, sample.groups[key]) for key in keys if key in sample.groups]
        labelled.append(("parent", roots[sample.id]))
        for group in labelled:
            first = seen.setdefault(group, assigned[sample.id])
            if first != assigned[sample.id]:
                pair = " and ".join(sorted({first, assigned[sample.id]}))
                raise ValueError(f"{group[0]} {group[1]!r} spans {pair}")


def _evidence(task: Task, members: list[Sample]) -> list[Annotation]:
    needed = TASK_SUPERVISION[task]
    return [
        note
        for sample in members
        for note in sample.annotations
        if note.supervises() and note.supervision in needed
    ]


def _check_target(task: Task, kept: list[Sample]) -> None:
    """An absent label denies its named taxon/category; a binary task needs one target."""
    targets = {
        ("taxon", note.taxon) if note.taxon is not None else ("category", note.category)
        for note in _evidence(task, kept)
        if note.taxon is not None or note.category is not None
    }
    if task in BINARY_TASKS and len(targets) > 1:
        raise ValueError(f"{task} needs one target taxon or category, found {sorted(targets)}")


def _evidence_gap(task: Task, members: list[Sample]) -> str | None:
    needed = TASK_SUPERVISION[task]
    if not needed:
        return None
    labels = {note.label for note in _evidence(task, members)}
    kinds = " or ".join(sorted(needed))
    missing = sorted({"present", "absent"} - labels) if task in BINARY_TASKS else []
    if not labels or missing:
        return f"{' '.join(missing[:1] + [kinds])} evidence"
    return None


def _counts(members: list[Sample], key: str) -> Counts:
    notes = [note for sample in members for note in sample.annotations if note.supervises()]
    return Counts(
        samples=len(members),
        groups=len({sample.groups[key] for sample in members}),
        labels=dict(sorted(Counter(note.label for note in notes).items())),
        reviews=dict(sorted(Counter(note.review for note in notes).items())),
        taxa=dict(sorted(Counter(note.taxon for note in notes if note.taxon).items())),
        categories=dict(sorted(Counter(note.category for note in notes if note.category).items())),
    )


def _by_split(
    kept: list[Sample], assigned: dict[str, SplitName], spec: ReleaseSpec
) -> dict[SplitName, list[Sample]]:
    by_split: dict[SplitName, list[Sample]] = {}
    for name in ("fit", "validation", "test"):
        members = [sample for sample in kept if assigned[sample.id] == name]
        if not members:
            raise ValueError(f"Split {name} is empty")
        if gap := _evidence_gap(spec.task, members):
            raise ValueError(f"Split {name} lacks {gap}")
        by_split[name] = members
    return by_split


def _check_consent(samples: list[Sample]) -> None:
    """A release trains and tests models, which a contributor must have permitted."""
    for sample in samples:
        given = sample.rights.consent
        if given and (reason := refusal(given.uses, given.withdrawn_at, "training")):
            raise ValueError(f"Refused {sample.id}: {reason}")


def build_release(
    samples: list[Sample], spec: ReleaseSpec, *, recorded_at: str
) -> tuple[Release, list[Sample]]:
    """The release record and its samples (sorted by id), or a refusal."""
    assigned = _assign(samples, spec)
    buffer, excluded = (None, {})
    if spec.buffer_m is not None:
        buffer, excluded = _buffer(samples, assigned, spec.buffer_m)
    kept = sorted((s for s in samples if s.id not in excluded), key=lambda s: s.id)
    _check_consent(kept)
    key = spec.split.group_key
    keys = list(dict.fromkeys([key, *spec.separate]))
    _check_separation(kept, assigned, keys, _lineage_roots(samples))
    _check_target(spec.task, kept)
    by_split = _by_split(kept, assigned, spec)
    snapshots: dict[str, set[str]] = {}
    for sample in kept:
        snapshots.setdefault(sample.source, set()).add(sample.snapshot)
    draft = Release(
        id="",
        release_format=2 if any(s.schema_version == 2 for s in kept) else 1,
        name=spec.name,
        task=spec.task,
        protocol=spec.protocol,
        split=spec.split,
        separate=sorted(set(spec.separate)),
        contract_schema_version=max(sample.schema_version for sample in kept),
        manifest_sha256=hashlib.sha256(manifest_bytes(kept)).hexdigest(),
        source_snapshots={source: sorted(values) for source, values in sorted(snapshots.items())},
        licenses=sorted({sample.rights.media_license for sample in kept}),
        buffer=buffer,
        splits={
            name: Members(
                samples=[sample.id for sample in members],
                groups=sorted({sample.groups[key] for sample in members}),
            )
            for name, members in by_split.items()
        },
        excluded=dict(sorted(excluded.items())),
        counts={name: _counts(members, key) for name, members in by_split.items()},
        test_status=spec.test_status,
        test_history=[
            StatusChange(status=spec.test_status, recorded_at=recorded_at, note="release created")
        ],
    )
    return draft.model_copy(update={"id": draft.content_id()}), kept


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _write_record(directory: Path, release: Release) -> None:
    write_atomic(directory / RELEASE, (release.model_dump_json(indent=2) + "\n").encode())


def write_release(
    directory: Path, samples: list[Sample], spec: ReleaseSpec, *, recorded_at: str | None = None
) -> Release:
    """Build and write a release into a new or empty directory."""
    if directory.exists() and any(directory.iterdir()):
        raise ValueError(f"Release directory must be empty: {directory}")
    release, kept = build_release(samples, spec, recorded_at=recorded_at or _now())
    directory.mkdir(parents=True, exist_ok=True)
    if write_manifest(directory / MANIFEST, kept) != release.manifest_sha256:
        raise ValueError("The written manifest differs from the release record")
    _write_record(directory, release)
    return release


def read_release(directory: Path) -> tuple[Release, list[Sample]]:
    """Read a release, refusing an edited record or an altered manifest."""
    release = Release.model_validate_json((directory / RELEASE).read_bytes())
    if release.content_id() != release.id:
        raise ValueError(f"Release {release.id} does not match its content")
    samples = read_manifest(directory / release.manifest, release.manifest_sha256)
    if max(sample.schema_version for sample in samples) != release.contract_schema_version:
        raise ValueError("Release contract schema version differs from its actual samples")
    listed = sorted(sample for members in release.splits.values() for sample in members.samples)
    if sorted(sample.id for sample in samples) != listed:
        raise ValueError(f"Release {release.id} splits do not list its manifest's samples")
    return release, samples


def record_test_status(
    directory: Path, status: TestStatus, *, note: str, recorded_at: str | None = None
) -> Release:
    """Append a test status change; a test that was inspected or used never becomes fresh."""
    release, _ = read_release(directory)
    _check_advance(release.test_status, status)
    change = StatusChange(status=status, recorded_at=recorded_at or _now(), note=note)
    updated = release.model_copy(
        update={"test_status": status, "test_history": [*release.test_history, change]}
    )
    _write_record(directory, Release.model_validate(updated.model_dump()))
    return updated
