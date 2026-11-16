"""Frozen dataset releases: exact samples, whole-group splits and a protected test.

A release is a directory holding `samples.jsonl` (the contract manifest) and a small
`release.json`. Whole groups are assigned to splits before anything is derived from them;
a release whose groups or parents span splits, or whose splits lack task evidence, is
refused, as is one keeping a photo its contributor did not permit for training (#60).
Whether the test is still a fresh holdout is recorded and can only advance.
"""

import hashlib
import math
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from weedz.consent import refusal
from weedz.contract import (
    TASK_SUPERVISION,
    Annotation,
    Sample,
    Task,
    require_task,
)
from weedz.gold import ReviewPolicy, promote_detection, validate_detection
from weedz.manifest import manifest_bytes, read_manifest, write_atomic, write_manifest
from weedz.release_assets import collect_assets, verify_assets
from weedz.release_evidence import checked_negatives
from weedz.release_models import (
    MANIFEST,
    RELEASE,
    STATUS_ORDER,
    Buffer,
    Counts,
    ExplicitSplit,
    Frozen,
    HashSplit,
    Members,
    Release,
    ReleaseName,
    ReleaseSpec,
    SplitName,
    SplitRule,
    StatusChange,
    TestStatus,
    _check_advance,
)
from weedz.release_scope import (
    Target,
    TargetScope,
    annotation_target,
    release_target_scope,
    task_annotations,
)
from weedz.release_storage import require_asset_destination, require_empty, staged_release
from weedz.rights_profiles import require_rights

__all__ = [
    "MANIFEST",
    "RELEASE",
    "STATUS_ORDER",
    "SPLITS",
    "BINARY_TASKS",
    "EARTH_RADIUS_M",
    "Buffer",
    "Counts",
    "ExplicitSplit",
    "Frozen",
    "HashSplit",
    "Members",
    "Release",
    "ReleaseName",
    "ReleaseSpec",
    "SplitName",
    "SplitRule",
    "StatusChange",
    "TestStatus",
    "build_release",
    "write_release",
    "read_release",
    "record_test_status",
]

# Protection order: the test is never trimmed, then validation, then fit.
SPLITS: tuple[SplitName, ...] = ("test", "validation", "fit")
# Tasks whose evaluation needs both labels in every split.
BINARY_TASKS = frozenset({"point_classification"})
EARTH_RADIUS_M = 6_371_000


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
    return [note for sample in members for note in task_annotations(sample, task)]


def _check_target(task: Task, kept: list[Sample]) -> None:
    """An absent label denies its named taxon/category; a binary task needs one target."""
    targets = {
        target for note in _evidence(task, kept) if (target := annotation_target(note)) is not None
    }
    if task in BINARY_TASKS and len(targets) > 1:
        raise ValueError(f"{task} needs one target taxon or category, found {sorted(targets)}")


def _evidence_gap(task: Task, members: list[Sample]) -> str | None:
    needed = TASK_SUPERVISION[task]
    if not needed:
        return None
    labels = {note.label for note in _evidence(task, members)}
    if any(checked_negatives(sample, task) for sample in members):
        labels.add("absent")
    kinds = " or ".join(sorted(needed))
    missing = sorted({"present", "absent"} - labels) if task in BINARY_TASKS else []
    checked = any(
        coverage.task == task and coverage.supervises()
        for sample in members
        for coverage in sample.completeness
    )
    if (not labels and not checked) or missing:
        return f"{' '.join(missing[:1] + [kinds])} evidence"
    return None


def _counts(members: list[Sample], key: str, task: Task) -> Counts:
    notes = [note for sample in members for note in sample.annotations if note.supervises()]
    return Counts(
        samples=len(members),
        groups=len({sample.groups[key] for sample in members}),
        labels=dict(sorted(Counter(note.label for note in notes).items())),
        reviews=dict(sorted(Counter(note.review for note in notes).items())),
        taxa=dict(sorted(Counter(note.taxon for note in notes if note.taxon).items())),
        categories=dict(sorted(Counter(note.category for note in notes if note.category).items())),
        checked_negatives=dict(
            sorted(
                Counter(
                    target for sample in members for target in checked_negatives(sample, task)
                ).items()
            )
        ),
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


def _review_targets(policy: ReviewPolicy | None) -> TargetScope | None:
    if policy is None:
        return None
    targets: list[Target] = [("taxon", name) for name in policy.taxa]
    targets.extend(("category", name) for name in policy.categories)
    return tuple(sorted(targets))


def build_release(
    samples: list[Sample], spec: ReleaseSpec, *, recorded_at: str
) -> tuple[Release, list[Sample]]:
    """The release record and its samples (sorted by id), or a refusal."""
    if spec.review_policy is not None:
        samples = [promote_detection(sample, spec.review_policy) for sample in samples]
    assigned = _assign(samples, spec)
    buffer, excluded = (None, {})
    if spec.buffer_m is not None:
        buffer, excluded = _buffer(samples, assigned, spec.buffer_m)
    kept = sorted((s for s in samples if s.id not in excluded), key=lambda s: s.id)
    _check_consent(kept)
    if spec.rights_profile is not None:
        for sample in kept:
            require_rights(sample, spec.rights_profile)
    key = spec.split.group_key
    extra_groups = spec.review_policy.required_groups if spec.review_policy else ()
    separate = sorted(set(spec.separate) | (set(extra_groups) - {key}))
    keys = list(dict.fromkeys([key, *separate]))
    _check_separation(kept, assigned, keys, _lineage_roots(samples))
    _check_target(spec.task, kept)
    target_scope = release_target_scope(
        spec.task, kept, targets=_review_targets(spec.review_policy)
    )
    by_split = _by_split(kept, assigned, spec)
    snapshots: dict[str, set[str]] = {}
    for sample in kept:
        snapshots.setdefault(sample.source, set()).add(sample.snapshot)
    draft = Release(
        id="",
        target_scope=target_scope,
        release_format=2
        if target_scope
        or any(s.schema_version == 2 for s in kept)
        or spec.review_policy is not None
        or spec.rights_profile is not None
        else 1,
        name=spec.name,
        task=spec.task,
        protocol=spec.protocol,
        split=spec.split,
        separate=separate,
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
        counts={name: _counts(members, key, spec.task) for name, members in by_split.items()},
        review_policy=spec.review_policy,
        rights_profile=spec.rights_profile,
        metadata_licenses=sorted({s.rights.metadata_license for s in kept})
        if spec.rights_profile is not None
        else None,
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
    directory: Path,
    samples: list[Sample],
    spec: ReleaseSpec,
    *,
    recorded_at: str | None = None,
    assets_root: Path | None = None,
) -> Release:
    """Publish one durable directory; gold releases require all referenced local assets."""
    require_empty(directory)
    if spec.review_policy is not None and assets_root is None:
        raise ValueError("A gold release needs assets_root to close its pinned assets")
    snapshots = [Sample.model_validate_json(sample.model_dump_json()) for sample in samples]
    release, kept = build_release(snapshots, spec, recorded_at=recorded_at or _now())
    assets = collect_assets(kept) if assets_root is not None else None
    if assets is not None:
        require_asset_destination(directory)
        fields = release.model_dump(mode="json") | {"assets": assets, "release_format": 2}
        release = Release.model_validate(fields)
        release = release.model_copy(update={"id": release.content_id()})
    with staged_release(directory, private=release.release_format != 1) as staging:
        if assets_root is not None and assets is not None:
            verify_assets(assets_root, assets, staging)
        if write_manifest(staging / MANIFEST, kept) != release.manifest_sha256:
            raise ValueError("The written manifest differs from the release record")
        _write_record(staging, release)
    return release


def read_release(directory: Path) -> tuple[Release, list[Sample]]:
    """Read a release, refusing an edited record or an altered manifest."""
    release = Release.model_validate_json((directory / RELEASE).read_bytes())
    if release.content_id() != release.id:
        raise ValueError(f"Release {release.id} does not match its content")
    samples = read_manifest(directory / release.manifest, release.manifest_sha256)
    if max(sample.schema_version for sample in samples) != release.contract_schema_version:
        raise ValueError("Release contract schema version differs from its actual samples")
    if (
        release_target_scope(release.task, samples, targets=_review_targets(release.review_policy))
        != release.target_scope
    ):
        raise ValueError("Release target scope differs from its sample evidence")
    listed = sorted(sample for members in release.splits.values() for sample in members.samples)
    if sorted(sample.id for sample in samples) != listed:
        raise ValueError(f"Release {release.id} splits do not list its manifest's samples")
    if release.assets is not None:
        if collect_assets(samples) != release.assets:
            raise ValueError("Release assets differ from its manifest/history references")
        verify_assets(directory, release.assets)
    _verify_review_policy(release, samples)
    return release, samples


def _verify_review_policy(release: Release, samples: list[Sample]) -> None:
    if release.rights_profile is not None:
        for sample in samples:
            require_rights(sample, release.rights_profile)
    if release.review_policy is None:
        return
    if release.assets is None:
        raise ValueError("A gold release must close its pinned assets")
    for sample in samples:
        require_task(sample, "detection")
        validate_detection(sample, release.review_policy)


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
