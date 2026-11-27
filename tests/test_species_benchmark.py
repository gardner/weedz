"""Cached species comparisons must not silently change the evaluation cohort."""

import pytest
from region_helpers import sample

from weedz.species_benchmark import FrameBatch, RegionBatch, compare_species


def inputs():
    record = sample(
        annotations=[
            {
                "id": "source:1",
                "supervision": "box",
                "box": [1, 2, 4, 6],
                "taxon": "Source species",
                "label": "present",
                "origin": "source",
            }
        ]
    )
    model = {"weights_sha256": "b" * 64, "labels_sha256": "c" * 64}
    topk = [
        {
            "taxon": "Unlabeled species",
            "score": 0.8,
            "score_kind": "closed_set_softmax_uncalibrated",
        },
        {"taxon": "Model species", "score": 0.1, "score_kind": "closed_set_softmax_uncalibrated"},
    ]
    frames = FrameBatch.model_validate(
        {
            "model": model,
            "manifest_sha256": "d" * 64,
            "predictions": [
                {
                    "sample_id": record.id,
                    "image_sha256": record.media.sha256,
                    "frame_topk": topk,
                    "tiles": [{"topk": topk}],
                }
            ],
        }
    )
    regions = RegionBatch.model_validate(
        {
            "model": model,
            "manifest_sha256": "d" * 64,
            "predictions": [
                {
                    "source_id": record.id,
                    "image_sha256": record.media.sha256,
                    "regions": [{"topk": topk}],
                }
            ],
        }
    )
    return record, frames, regions


def test_partial_labels_measure_positive_recall_without_filtering_prediction_vocabulary():
    record, frames, regions = inputs()
    report = compare_species([record], frames, regions, {"Source species": "Model species"}, 1)
    assert report["positive_image_taxon_pairs"] == 1
    for method in report["methods"].values():
        assert method["recovered_positive_pairs"] == 0
        assert "precision" not in method
    assert report["rows"][0]["rankings"]["tiles_max_score"] == ["Unlabeled species"]
    assert report["candidate_coverage"]["tiles"]["available_positive_pairs"] == 1


@pytest.mark.parametrize("problem", ["missing", "duplicate", "pixels", "weights", "labels"])
def test_mismatched_or_duplicated_prediction_evidence_is_rejected(problem: str):
    record, frames, regions = inputs()
    data = regions.model_dump()
    if problem == "missing":
        data["predictions"] = []
    elif problem == "duplicate":
        data["predictions"] *= 2
    elif problem == "pixels":
        data["predictions"][0]["image_sha256"] = "f" * 64
    else:
        data["model"][f"{problem}_sha256"] = "f" * 64
    with pytest.raises(ValueError):
        compare_species(
            [record],
            frames,
            RegionBatch.model_validate(data),
            {"Source species": "Model species"},
            5,
        )


def test_missing_taxonomy_mapping_is_not_silently_removed_from_denominator():
    record, frames, regions = inputs()
    with pytest.raises(ValueError, match="mapping"):
        compare_species([record], frames, regions, {}, 5)


def test_model_origin_labels_do_not_become_positive_truth():
    record, frames, regions = inputs()
    note = record.annotations[0].model_copy(update={"origin": "model", "model": "example"})
    record = record.model_copy(update={"annotations": (note,)})
    with pytest.raises(ValueError, match="source-positive"):
        compare_species([record], frames, regions, {"Source species": "Model species"}, 5)


def test_repeated_boxes_of_one_species_count_as_one_image_species_pair():
    record, frames, regions = inputs()
    second = record.annotations[0].model_copy(update={"id": "source:2"})
    record = record.model_copy(update={"annotations": (*record.annotations, second)})
    report = compare_species([record], frames, regions, {"Source species": "Model species"}, 5)
    assert report["positive_image_taxon_pairs"] == 1
    assert report["methods"]["regions_max_score"]["recovered_positive_pairs"] == 1


def test_different_prediction_manifests_cannot_be_compared():
    record, frames, regions = inputs()
    regions = regions.model_copy(update={"manifest_sha256": "f" * 64})
    with pytest.raises(ValueError, match="common manifest"):
        compare_species([record], frames, regions, {"Source species": "Model species"}, 5)


def test_duplicate_assets_under_distinct_ids_cannot_inflate_the_benchmark():
    record, frames, regions = inputs()
    second = record.model_copy(update={"id": "cwfid:2", "source_id": "2"})
    frames.predictions.append(frames.predictions[0].model_copy(update={"sample_id": second.id}))
    regions.predictions.append(regions.predictions[0].model_copy(update={"source_id": second.id}))
    with pytest.raises(ValueError, match="Duplicate encoded image"):
        compare_species([record, second], frames, regions, {"Source species": "Model species"}, 5)
