"""Task/target coverage eligibility, separate from stricter gold-review promotion."""

from dataclasses import dataclass
from typing import Literal

from weedz.contract import Completeness, Sample
from weedz.region_evaluation.truth import TruthOrigin, eligible_positive

type Task = Literal["detection", "segmentation"]


@dataclass(frozen=True)
class Target:
    kind: Literal["category", "taxon"]
    name: str
    source: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"category", "taxon"} or not self.name.strip():
            raise ValueError("Need a named category or taxon target")
        if self.kind == "category" and not self.source:
            raise ValueError("A functional category requires its source namespace")
        if self.kind == "taxon" and self.source is not None:
            raise ValueError("Taxonomic mapping must be explicit before assessment")

    def covered_by(self, coverage: Completeness, sample: Sample) -> bool:
        if self.kind == "category":
            return self.source == sample.source and self.name in coverage.categories
        return self.name in coverage.taxa


@dataclass(frozen=True)
class ScopeAssessment:
    exhaustive: bool
    completeness_ids: tuple[str, ...]
    origins: tuple[str, ...]


def assess_scope(
    sample: Sample, *, task: Task, target: Target, origin: TruthOrigin = "source"
) -> ScopeAssessment:
    """Documented source coverage may supervise without claiming accepted gold.

    The manifest validates each coverage claim's media identity. No annotation count,
    classifier decision or model mask can establish completeness here.
    """
    if task not in {"detection", "segmentation"}:
        raise ValueError("Need a detection or segmentation task")
    if _unresolved(sample, target, origin):
        return ScopeAssessment(False, (), ())
    eligible = [
        coverage
        for coverage in sample.completeness
        if coverage.task == task
        and coverage.origin == origin
        and coverage.media_sha256 == sample.media.sha256
        and target.covered_by(coverage, sample)
        and coverage.supervises()
    ]
    return ScopeAssessment(
        bool(eligible),
        tuple(sorted(coverage.id for coverage in eligible)),
        tuple(sorted({coverage.origin for coverage in eligible})),
    )


def _unresolved(sample: Sample, target: Target, origin: TruthOrigin) -> bool:
    claims = [
        annotation
        for annotation in sample.annotations
        if annotation.origin == origin
        and annotation.review != "rejected"
        and (origin == "source" or annotation.review == "accepted")
        and (
            annotation.taxon == target.name
            if target.kind == "taxon"
            else sample.source == target.source and annotation.category == target.name
        )
    ]
    if any(annotation.label == "unknown" for annotation in claims):
        return True
    absent = any(
        annotation.label == "absent" and annotation.supervision == "image_class"
        for annotation in claims
    )
    return absent and any(eligible_positive(annotation, origin=origin) for annotation in claims)
