"""Reviewed scoped negatives need no fictitious boxes or masks in any split."""

import pytest
from test_release import WHEN, sample, spec

from weedz.contract import Completeness, revise_sample
from weedz.release import build_release


@pytest.mark.parametrize("task", ["detection", "segmentation"])
def test_all_negative_splits_accept_checked_scoped_completeness(task):
    records = []
    for number, site in enumerate(("a", "b", "c", "d")):
        base = sample(number, site)
        coverage = Completeness.model_validate(
            dict(
                id="checked",
                task=task,
                taxa=["Ulex europaeus"],
                status="exhaustive",
                origin="reviewer",
                author="fixture-reviewer",
                review="accepted",
                reviewers=["fixture-reviewer"],
                recorded_at=WHEN,
                media_sha256="a" * 64,
                evidence={"protocol": "synthetic whole-image fixture"},
            )
        )
        records.append(
            revise_sample(
                base,
                tasks=[task],
                annotations=[],
                completeness=[coverage],
                media=base.media.model_copy(update={"sha256": "a" * 64}),
            )
        )
    release, kept = build_release(records, spec(task=task), recorded_at=WHEN)
    assert release.release_format == release.contract_schema_version == 2
    assert all(not record.annotations for record in kept)
    assert all(release.splits[name].samples for name in ("fit", "validation", "test"))
