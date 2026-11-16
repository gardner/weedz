"""Named completeness is checked per image, never pooled across different images."""

from typing import Literal

from weedz.contract import TASK_SUPERVISION, Annotation, Sample, Task, Text

type Target = tuple[Literal["taxon", "category"], Text]
type TargetScope = tuple[Target, ...]


def annotation_target(note: Annotation) -> Target | None:
    if note.taxon is not None:
        return "taxon", note.taxon
    return ("category", note.category) if note.category is not None else None


def task_annotations(sample: Sample, task: Task) -> tuple[Annotation, ...]:
    return tuple(
        note
        for note in sample.annotations
        if note.supervises() and note.supervision in TASK_SUPERVISION[task]
    )


def checked_scope(sample: Sample, task: Task) -> frozenset[Target]:
    targets: set[Target] = set()
    for coverage in sample.completeness:
        if coverage.task == task and coverage.supervises():
            targets.update(("taxon", name) for name in coverage.taxa)
            targets.update(("category", name) for name in coverage.categories)
    return frozenset(targets)


def release_target_scope(
    task: Task, samples: list[Sample], *, targets: TargetScope | None = None
) -> TargetScope | None:
    """Scope for the completeness fallback, omitted for geometry-only legacy releases.

    Ordinary partial geometry remains useful evidence; it is not thereby exhaustive.
    Gold callers may supply their explicit policy targets rather than inferring them.
    """
    if not TASK_SUPERVISION[task]:
        return None
    negatives = [sample for sample in samples if not task_annotations(sample, task)]
    if not negatives:
        return None
    required = (
        frozenset(targets)
        if targets is not None
        else frozenset(
            target
            for sample in samples
            for note in task_annotations(sample, task)
            if note.label == "present" and (target := annotation_target(note)) is not None
        )
    )
    if not required:
        scopes = [checked_scope(sample, task) for sample in samples]
        if not scopes[0] or any(scope != scopes[0] for scope in scopes):
            raise ValueError(
                "An all-negative release needs one common per-image checked target scope"
            )
        required = scopes[0]
    for sample in negatives:
        if not required <= checked_scope(sample, task):
            raise ValueError(
                f"Completeness scope for {sample.id} does not cover all release targets"
            )
    return tuple(sorted(required))
