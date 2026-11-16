"""Aggregates use declared denominators and never count aliases as independent images."""

from weedz.region_evaluation.aggregate import aggregate_boxes


def case(identity: str, sha: str, labelled: int, matched: int) -> dict:
    return {
        "sample_id": identity,
        "image_sha256": sha,
        "proposal_status": "ok",
        "measurements": [
            {
                "budget": 10,
                "iou_threshold": 0.5,
                "actual_proposals": 2,
                "labelled_regions": labelled,
                "matched_labelled_regions": matched,
                "missed_labelled_regions": labelled - matched,
                "unmatched_proposals": 2 - matched,
                "identification": None,
            }
        ],
    }


def test_micro_labelled_recall_and_macro_image_recall_use_different_units():
    result = aggregate_boxes([case("one", "a" * 64, 2, 1), case("two", "b" * 64, 1, 0)])
    score = result["aggregate"][0]
    assert score["labelled_regions"] == 3
    assert score["labelled_region_recall"] == 1 / 3
    assert score["macro_image_labelled_recall"] == 0.25
    assert result["record_count"] == result["unique_image_count"] == 2


def test_duplicate_image_aliases_block_primary_aggregate_without_discarding_cases():
    result = aggregate_boxes([case("one", "a" * 64, 2, 1), case("alias", "a" * 64, 1, 0)])
    assert result["record_count"] == 2 and result["unique_image_count"] == 1
    assert result["aggregate"] is None
    assert result["duplicate_image_groups"] == [["one", "alias"]]


def test_zero_label_images_do_not_become_perfect_negatives():
    result = aggregate_boxes([case("empty", "a" * 64, 0, 0)])
    assert result["aggregate"][0]["labelled_region_recall"] is None
    assert result["aggregate"][0]["macro_image_labelled_recall"] is None
    assert result["aggregate"][0]["images_with_labelled_regions"] == 0
