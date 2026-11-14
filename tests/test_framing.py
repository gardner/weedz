"""Whole-frame versus tile readouts of the same window embeddings (#12); no model."""

from typing import Any

import numpy as np
import pytest

from weedz.discovery.framing import (
    Label,
    arm_windows,
    at_budget,
    compare,
    independent_labels,
    lookalikes_reached,
    overlap,
    ranked,
    source_labels,
    suggest,
)
from weedz.discovery.inference import region_boxes, summarize_scores
from weedz.discovery.records import SPECIES

TARGETS = list(SPECIES)
WIDTH, HEIGHT = 100, 80  # whole frame + 6 tiles
WINDOWS = len(region_boxes(WIDTH, HEIGHT))
WEAK = [0.10, 0.10, 0.10, 0.20]


def result(rows: list[list[float]], featureless: list[int] | None = None) -> dict[str, Any]:
    """A revision 4 screening result: per window, three targets then comparisons.

    Windows after those given are weak everywhere (margin -0.1)."""
    width = len(rows[0])
    rows = rows + [WEAK + [0.0] * (width - 4)] * (WINDOWS - len(rows))
    return {
        "window_similarities": rows,
        "width": WIDTH,
        "height": HEIGHT,
        "featureless_windows": featureless or [],
    }


# Window 0 (frame) favours gorse; tile 1 favours pampas strongly; tile 2 is weak.
FRAME_GORSE_TILE_PAMPAS = result(
    [[0.10, 0.10, 0.30, 0.20], [0.10, 0.40, 0.10, 0.20], [0.15, 0.10, 0.10, 0.20]]
)


def test_arms_choose_which_windows_may_rank_a_species() -> None:
    assert arm_windows("whole_frame", 4, []) == [True, False, False, False]
    assert arm_windows("tiles", 4, [2]) == [False, True, False, True]
    assert arm_windows("frame_and_tiles", 4, [2]) == [True, True, False, True]


def test_unknown_arm_is_refused() -> None:
    with pytest.raises(KeyError):
        arm_windows("segments", 3, [])  # type: ignore[arg-type]


def test_each_arm_reads_the_same_embeddings_differently() -> None:
    frame = suggest(FRAME_GORSE_TILE_PAMPAS, "whole_frame")
    tiles = suggest(FRAME_GORSE_TILE_PAMPAS, "tiles")
    both = suggest(FRAME_GORSE_TILE_PAMPAS, "frame_and_tiles")
    assert frame and tiles and both
    assert (frame["species"], frame["margin"]) == ("Ulex europaeus", pytest.approx(0.10))
    assert (tiles["species"], tiles["margin"]) == ("Cortaderia selloana", pytest.approx(0.20))
    assert both["species"] == "Cortaderia selloana"
    assert tiles["box"] == list(region_boxes(WIDTH, HEIGHT)[1])


def test_frame_and_tiles_reproduces_the_screening_ranking() -> None:
    sample = result(
        [[0.10, 0.10, 0.30, 0.20], [0.50, 0.40, 0.10, 0.20], [0.15, 0.10, 0.10, 0.20]], [1]
    )
    boxes = region_boxes(WIDTH, HEIGHT)
    eligible = [index != 1 for index in range(WINDOWS)]
    screened = summarize_scores(
        np.array(sample["window_similarities"]), boxes, TARGETS + ["x"], 3, eligible
    )
    both = suggest(sample, "frame_and_tiles")
    assert both is not None
    assert both["species"] == screened["best_species"]
    assert both["margin"] == screened["margin"]
    assert both["box"] == screened["box"]


def test_featureless_tiles_cannot_rank_and_all_featureless_leaves_tiles_unranked() -> None:
    sample = result([[0.10, 0.10, 0.30, 0.20], [0.10, 0.40, 0.10, 0.20]], list(range(1, WINDOWS)))
    assert suggest(sample, "tiles") is None
    frame = suggest(sample, "frame_and_tiles")
    assert frame and frame["species"] == "Ulex europaeus"


def test_a_subject_comparison_column_counts_as_a_comparison() -> None:
    rows = [[0.1, 0.1, 0.3, 0.2, 0.35], [0.1, 0.4, 0.1, 0.2, 0.1]]
    frame = suggest(result(rows), "whole_frame")
    assert frame and frame["margin"] == pytest.approx(-0.05)


def test_mismatched_window_count_is_refused() -> None:
    with pytest.raises(ValueError, match="windows"):
        suggest({**FRAME_GORSE_TILE_PAMPAS, "width": 1000, "height": 200}, "tiles")


def test_queue_ranks_by_margin_then_id_and_leaves_out_unranked_photos() -> None:
    queue = ranked(
        {
            "b": {"species": "Ulex europaeus", "margin": 0.1, "box": []},
            "a": {"species": "Ulex europaeus", "margin": 0.1, "box": []},
            "c": {"species": "Clematis vitalba", "margin": 0.3, "box": []},
            "d": None,
        }
    )
    assert [item["photo_id"] for item in queue] == ["c", "a", "b"]
    assert queue[0] == {"photo_id": "c", "species": "Clematis vitalba", "margin": 0.3}


QUEUE = [
    {"photo_id": "p1", "species": "Ulex europaeus", "margin": 0.3},
    {"photo_id": "p2", "species": "Clematis vitalba", "margin": 0.2},
    {"photo_id": "p3", "species": "Cortaderia selloana", "margin": 0.1},
    {"photo_id": "p4", "species": "Ulex europaeus", "margin": 0.0},
]


def test_budget_counts_found_weeds_only_when_the_suggestion_names_them() -> None:
    labels = [
        Label("p1", "Ulex europaeus", True),  # found
        Label("p2", "Ulex europaeus", True),  # reached, but suggested as clematis
        Label("p2", "Clematis vitalba", False),  # known false alarm
        Label("p4", "Ulex europaeus", True),  # beyond the budget
    ]
    measured = at_budget(QUEUE, labels, 3)
    assert measured == {
        "budget": 3,
        "reviewed": 3,
        "labelled_present": 3,
        "found": 1,
        "recall": pytest.approx(1 / 3),
        "known_false_alarms": 1,
        "precision": pytest.approx(0.5),
        "unlabelled": 1,
    }


def test_budget_without_labels_is_not_measurable_rather_than_zero() -> None:
    measured = at_budget(QUEUE, [], 2)
    assert measured["recall"] is None and measured["precision"] is None
    assert measured["unlabelled"] == 2 and measured["found"] == 0


def test_budget_beyond_the_queue_reviews_what_there_is() -> None:
    assert at_budget(QUEUE, [], 10)["reviewed"] == 4


def test_lookalikes_reaching_the_budget_as_the_weed_they_resemble() -> None:
    resembles = {"p1": "Ulex europaeus", "p3": "Clematis vitalba", "p4": "Ulex europaeus"}
    assert lookalikes_reached(QUEUE, resembles, 3) == 1


def test_overlap_counts_photos_shared_by_two_queues_at_a_budget() -> None:
    other = [QUEUE[2], QUEUE[0], QUEUE[3], QUEUE[1]]
    assert overlap(QUEUE, other, 2) == 1
    assert overlap(QUEUE, other, 4) == 4


def example(taxon: str, label: str, eligible: bool, photo: str = "p1") -> dict[str, Any]:
    return {
        "sample_id": f"inaturalist:{photo}",
        "taxon": taxon,
        "label": label,
        "uses": {"evaluation": {"eligible": eligible, "reason": ""}},
    }


def test_independent_labels_use_only_evaluation_eligible_watchlist_examples() -> None:
    examples = [
        example("Ulex europaeus", "present", True),
        example("Clematis vitalba", "present", False),  # e.g. an unaccepted suggestion
        example("Rubus fruticosus", "present", True, "p2"),  # not on the watchlist
        example("Cortaderia selloana", "absent", True, "p3"),
    ]
    assert independent_labels(examples, {}, {"p1", "p2", "p3"}) == [
        Label("p1", "Ulex europaeus", True),
        Label("p3", "Cortaderia selloana", False),
    ]


def test_agreeing_blind_audits_label_presence_or_absence_of_every_target() -> None:
    audits = {
        "found": {"ann": "Ulex europaeus", "bo": "Ulex europaeus"},
        "clear": {"ann": "none"},
        "disputed": {"ann": "none", "bo": "Clematis vitalba"},
        "unsure": {"ann": "unsure"},
        "unsampled": {"ann": "Clematis vitalba"},
    }
    sample = {"found", "clear", "disputed", "unsure"}
    labels = independent_labels([], audits, sample)
    assert Label("found", "Ulex europaeus", True) in labels
    assert {label for label in labels if label.photo_id == "clear"} == {
        Label("clear", species, False) for species in SPECIES
    }
    assert {label.photo_id for label in labels} == {"found", "clear"}


def test_source_labels_are_reference_subjects_only() -> None:
    photos = [
        {"id": "r", "cohort": "reference", "reference_species": "Ulex europaeus"},
        {"id": "i", "cohort": "incidental", "reference_species": ""},
        {"id": "l", "cohort": "lookalike", "lookalike_of": "Ulex europaeus"},
    ]
    assert source_labels(photos) == [Label("r", "Ulex europaeus", True)]


def test_compare_reports_every_arm_and_budget_on_both_queues() -> None:
    gorse_frame = FRAME_GORSE_TILE_PAMPAS
    pampas_frame = result(
        [[0.10, 0.35, 0.10, 0.20], [0.10, 0.10, 0.10, 0.20], [0.10, 0.10, 0.10, 0.20]]
    )
    photos = [
        {"id": "i1", "cohort": "incidental"},
        {"id": "r1", "cohort": "reference", "reference_species": "Cortaderia selloana"},
        {"id": "h1", "cohort": "lookalike", "lookalike_of": "Ulex europaeus"},
    ]
    results = {"i1": gorse_frame, "r1": pampas_frame, "h1": gorse_frame}
    found = compare(results, photos, [Label("i1", "Cortaderia selloana", True)], [1, 2])
    assert set(found["arms"]) == {"whole_frame", "tiles", "frame_and_tiles"}
    whole = found["arms"]["whole_frame"]
    assert whole["windows_per_photo"] == 1
    assert found["arms"]["tiles"]["windows_per_photo"] == WINDOWS - 1
    incidental = whole["incidental"]["budgets"]
    assert [row["budget"] for row in incidental] == [1, 2]
    assert incidental[0]["found"] == 0  # whole frame says gorse
    assert found["arms"]["tiles"]["incidental"]["budgets"][0]["found"] == 1
    pooled = whole["pooled"]["budgets"][0]
    assert pooled["found"] == 1 and pooled["lookalikes_reached"] == 0
    assert whole["pooled"]["budgets"][1]["lookalikes_reached"] == 1
    assert found["overlap"]["incidental"]["whole_frame|tiles"] == [1, 1]
    assert found["photos"]["i1"]["tiles"]["species"] == "Cortaderia selloana"
    assert found["labels"] == {"independent": 1, "source_subject": 1, "lookalike_photos": 1}


def test_contradicting_labels_are_dropped_and_duplicates_kept_once() -> None:
    examples = [
        example("Ulex europaeus", "present", True, "clear"),
        example("Clematis vitalba", "present", True, "found"),
    ]
    audits = {"clear": {"ann": "none"}, "found": {"ann": "Clematis vitalba"}}
    labels = independent_labels(examples, audits, {"clear", "found"})
    assert Label("clear", "Ulex europaeus", True) not in labels
    assert Label("clear", "Ulex europaeus", False) not in labels
    assert Label("clear", "Clematis vitalba", False) in labels
    assert labels.count(Label("found", "Clematis vitalba", True)) == 1


def test_independent_labels_off_the_incidental_queue_are_not_counted() -> None:
    photos = [
        {"id": "i1", "cohort": "incidental"},
        {"id": "r1", "cohort": "reference", "reference_species": "Ulex europaeus"},
    ]
    results = {"i1": FRAME_GORSE_TILE_PAMPAS, "r1": FRAME_GORSE_TILE_PAMPAS}
    found = compare(results, photos, [Label("r1", "Ulex europaeus", True)], [1])
    assert found["labels"]["independent"] == 0
    row = found["arms"]["whole_frame"]["incidental"]["budgets"][0]
    assert row["labelled_present"] == 0 and row["recall"] is None


def test_reviewed_examples_count_only_on_the_rank_independent_audit_sample() -> None:
    """Ranked review reaches photos in margin order, so its findings would favour the
    arm that ordered the queue; only the blind sample is chosen independently of rank."""
    examples = [
        example("Ulex europaeus", "present", True, "sampled"),
        example("Ulex europaeus", "present", True, "ranked"),
    ]
    assert independent_labels(examples, {}, {"sampled"}) == [
        Label("sampled", "Ulex europaeus", True)
    ]
