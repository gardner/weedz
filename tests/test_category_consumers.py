"""Functional categories remain named targets, distinct from scientific taxa."""

import pytest
from test_reference import note
from test_reference import sample as reference_sample
from test_release import WHEN, sites, spec

from weedz.contract import Sample
from weedz.reference import collection, examples
from weedz.release import build_release


def categorical_records(mixed=False):
    records = []
    for sample in sites("a", "b", "c", "d"):
        raw = sample.model_dump(mode="json")
        raw["annotations"][0].update(
            taxon=None,
            category=("crop" if mixed and raw["annotations"][0]["label"] == "absent" else "weed"),
        )
        records.append(Sample.model_validate(raw))
    return records


def test_binary_point_release_refuses_different_functional_targets():
    with pytest.raises(ValueError, match="one target"):
        build_release(categorical_records(mixed=True), spec(), recorded_at=WHEN)


def test_category_only_release_counts_are_named_without_changing_legacy_counts():
    record, _ = build_release(categorical_records(), spec(), recorded_at=WHEN)
    assert record.counts["fit"].model_dump(mode="json")["categories"] == {"weed": 4}
    legacy, _ = build_release(sites("a", "b", "c", "d"), spec(), recorded_at=WHEN)
    assert "categories" not in legacy.counts["fit"].model_dump(mode="json")


def test_reference_examples_and_coverage_keep_categories_separate():
    functional = reference_sample(note(taxon=None, category="weed"))
    assert examples([functional])[0]["category"] == "weed"
    result = collection("functional", [functional])
    assert result["category_coverage"]["weed"]["training"]["photos"] == 1
    assert result["coverage"] == {}
    legacy = collection("legacy", [reference_sample()])
    assert "category_coverage" not in legacy
    assert "category" not in legacy["examples"][0]


def test_explicit_mapped_taxon_is_authoritative_over_original_source_categories():
    records = []
    for sample in categorical_records(mixed=True):
        raw = sample.model_dump(mode="json")
        raw["annotations"][0]["taxon"] = "Euphorbia esula"
        records.append(Sample.model_validate(raw))
    release, _ = build_release(records, spec(), recorded_at=WHEN)
    assert release.counts["fit"].taxa == {"Euphorbia esula": 4}
    assert release.counts["fit"].categories == {"crop": 2, "weed": 2}


def test_unmapped_category_is_not_a_taxon_even_when_text_matches():
    records = []
    for index, sample in enumerate(categorical_records()):
        raw = sample.model_dump(mode="json")
        raw["annotations"][0].update(
            taxon="Euphorbia esula" if index % 2 else None, category="Euphorbia esula"
        )
        records.append(Sample.model_validate(raw))
    with pytest.raises(ValueError, match="one target"):
        build_release(records, spec(), recorded_at=WHEN)
