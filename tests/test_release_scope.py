"""Whole-image completeness is scoped per image, never pooled into false negatives."""

import pytest
from test_release import WHEN, sample, spec

from weedz.contract import Annotation, Completeness, revise_sample
from weedz.release import build_release


def positive(number, site, taxon):
    base = sample(number, site)
    note = Annotation(
        id="box", supervision="box", taxon=taxon, label="present", box=(0, 0, 2, 2), origin="source"
    )
    return revise_sample(base, tasks=["detection"], annotations=[note])


def negative(number, site, scopes):
    base = sample(number, site)
    coverages = [
        Completeness(
            id=f"coverage-{i}",
            task="detection",
            taxa=tuple(taxa),
            status=status,
            origin="source",
            media_sha256="a" * 64,
            evidence={"protocol": "synthetic source protocol"},
        )
        for i, (taxa, status) in enumerate(scopes)
    ]
    return revise_sample(
        base,
        tasks=["detection"],
        annotations=[],
        completeness=coverages,
        media=base.media.model_copy(update={"sha256": "a" * 64}),
    )


def freeze(records):
    return build_release(records, spec(task="detection"), recorded_at=WHEN)[0]


def test_other_taxon_completeness_cannot_become_a_detector_holdout():
    records = [
        positive(0, "a", "Cytisus scoparius"),
        positive(1, "b", "Cytisus scoparius"),
        negative(2, "c", [(("Ulex europaeus",), "exhaustive")]),
        negative(3, "d", [(("Ulex europaeus",), "exhaustive")]),
    ]
    with pytest.raises(ValueError, match="scope"):
        freeze(records)


def test_different_negative_images_cannot_pool_their_checked_targets():
    records = [
        positive(0, "a", "A"),
        positive(1, "b", "B"),
        negative(2, "c", [(("A",), "exhaustive")]),
        negative(3, "c", [(("B",), "exhaustive")]),
        negative(4, "d", [(("A", "B"), "exhaustive")]),
    ]
    with pytest.raises(ValueError, match="scope"):
        freeze(records)


def test_within_image_union_is_valid_and_is_visible_in_release_scope():
    records = [
        positive(0, "a", "A"),
        positive(1, "b", "B"),
        negative(2, "c", [(("A",), "exhaustive"), (("B",), "exhaustive")]),
        negative(3, "d", [(("A", "B"), "exhaustive")]),
    ]
    release = freeze(records)
    assert release.target_scope == (("taxon", "A"), ("taxon", "B"))
    assert release.release_format == 2


def test_partial_coverage_does_not_complete_another_target():
    records = [
        positive(0, "a", "A"),
        positive(1, "b", "B"),
        negative(2, "c", [(("A",), "exhaustive"), (("B",), "partial")]),
        negative(3, "d", [(("A", "B"), "exhaustive")]),
    ]
    with pytest.raises(ValueError, match="scope"):
        freeze(records)


def test_all_negative_releases_require_one_common_per_image_scope():
    records = [
        negative(i, site, [((taxon,), "exhaustive")])
        for i, (site, taxon) in enumerate((("a", "A"), ("b", "B"), ("c", "A"), ("d", "A")))
    ]
    with pytest.raises(ValueError, match="scope"):
        freeze(records)
