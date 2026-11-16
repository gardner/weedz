"""Localisation misses and conditional identification errors have different denominators."""

from region_helpers import sample

from weedz.region_evaluation.identification import score_identification
from weedz.region_evaluation.matching import match_regions
from weedz.region_evaluation.taxonomy import TaxonomyMapping
from weedz.region_evaluation.truth import LabelledBox


def inputs():
    truth = [LabelledBox("source:1", (0, 0, 2, 2), "Species alba", None, "source", "unreviewed")]
    proposed = [{"id": "proposal:1"}, {"id": "proposal:2"}]
    names = {row["id"]: {"taxon": "Species alba L."} for row in proposed}
    taxonomy = TaxonomyMapping("a" * 64, "cwfid", "b" * 64, {"Species alba": "Species alba L."})
    return truth, proposed, names, taxonomy


def test_duplicates_are_not_false_alarms_under_incomplete_labels():
    truth, proposed, names, taxonomy = inputs()
    result = score_identification(
        sample(), truth, proposed, names, taxonomy, match_regions([[1, 1]], threshold=0.5)
    )
    assert result["conditional_top1_correct"] == 1
    assert result["conditional_top1_count"] == 1
    assert result["assessed_false_alarm_regions"] == 0
    assert result["unassessed_false_alarm_regions"] == 2
    assert result["verified_negative_targets"] == []


def test_explicit_complete_scope_supports_duplicate_false_alarm_count():
    truth, proposed, names, taxonomy = inputs()
    record = sample(
        completeness=[
            {
                "id": "coverage:1",
                "media_sha256": "a" * 64,
                "task": "detection",
                "taxa": ["Species alba"],
                "status": "exhaustive",
                "origin": "source",
                "evidence": {"protocol_sha256": "c" * 64},
            }
        ]
    )
    result = score_identification(
        record, truth, proposed, names, taxonomy, match_regions([[1, 1]], threshold=0.5)
    )
    assert result["assessed_false_alarm_regions"] == 1
    assert result["unassessed_false_alarm_regions"] == 0


def test_unlocalised_label_is_not_hidden_by_conditional_accuracy():
    truth, proposed, names, taxonomy = inputs()
    result = score_identification(
        sample(), truth, proposed, names, taxonomy, match_regions([[0.1, 0.1]], threshold=0.5)
    )
    assert result["conditional_top1_accuracy"] is None
    assert result["unlocalised_supported_labels"] == 1
    assert result["correctly_identified_labelled_recall"] == 0


def test_negative_target_uses_only_predictions_inside_the_declared_budget():
    _, proposed, names, taxonomy = inputs()
    names[proposed[0]["id"]]["taxon"] = "Species rubra A."
    record = sample(
        completeness=[
            {
                "id": "coverage:1",
                "media_sha256": "a" * 64,
                "task": "detection",
                "taxa": ["Species alba"],
                "status": "exhaustive",
                "origin": "source",
                "evidence": {"protocol_sha256": "c" * 64},
            }
        ]
    )
    result = score_identification(
        record,
        [],
        proposed[:1],
        names,
        taxonomy,
        match_regions([], threshold=0.5, proposal_count=1),
    )
    assert result["verified_negative_targets"][0]["correct_negative"] is True
