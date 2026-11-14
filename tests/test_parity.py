"""Does an optimised model still rank photos like the validated reference (#52)? No model."""

from typing import Any

import pytest

from weedz.discovery.parity import (
    THRESHOLDS,
    compare,
    encoding_cost,
    queue_change,
    readout,
)

CV, CS, UE = "Clematis vitalba", "Cortaderia selloana", "Ulex europaeus"
SIZE = 10  # whole frame + 4 tiles


def result(cv: float, cs: float, ue: float, comparison: float = 0.0) -> dict[str, Any]:
    """Every window scores the three targets, then one comparison label, the same way."""
    return {
        "window_similarities": [[cv, cs, ue, comparison]] * 5,
        "width": SIZE,
        "height": SIZE,
        "featureless_windows": [],
    }


def photo(pid: str, cohort: str = "incidental", **extra: str) -> dict[str, Any]:
    return {"id": pid, "cohort": cohort, **extra}


def incidental(count: int, start: float = -0.05) -> dict[str, dict[str, Any]]:
    """Incidental photos with clearly separated gorse margins, best first."""
    return {f"i{n:02}": result(-0.2, -0.2, start - 0.01 * n) for n in range(count)}


def test_readout_gives_best_species_and_every_margin() -> None:
    found = readout(result(0.1, 0.3, 0.2, comparison=0.25))
    assert found["species"] == CS
    assert found["margin"] == pytest.approx(0.05)
    assert found["margins"] == pytest.approx({CV: -0.15, CS: 0.05, UE: -0.05})


def test_readout_refuses_scores_for_other_windows() -> None:
    bad = result(0.1, 0.2, 0.3) | {"window_similarities": [[0.1, 0.2, 0.3, 0.0]] * 3}
    with pytest.raises(ValueError, match="windows"):
        readout(bad)


def test_identical_scores_pass_every_check() -> None:
    reference = incidental(25)
    photos = [photo(pid) for pid in reference]
    report = compare(reference, reference, photos)
    assert report["passed"] is True
    assert report["top_suggestion"] == {"agree": 25, "of": 25, "changed": []}
    assert report["margins"]["max_abs_drift"] == 0
    assert all(check["passed"] for check in report["checks"].values())
    assert [row["shared"] for row in report["queues"]["incidental"]] == [5, 10, 20]


def test_compare_needs_the_same_photos_from_both_models() -> None:
    reference = incidental(3)
    with pytest.raises(ValueError, match="same photos"):
        compare(reference, dict(list(reference.items())[:2]), [photo(p) for p in reference])


def test_small_drift_within_the_limit_still_passes() -> None:
    reference = incidental(10)
    candidate = {
        pid: result(-0.2, -0.2, r["window_similarities"][0][2] + 0.004)
        for pid, r in reference.items()
    }
    report = compare(reference, candidate, [photo(pid) for pid in reference])
    assert report["margins"]["max_abs_drift"] == pytest.approx(0.004)
    assert report["passed"] is True


def test_margin_drift_beyond_the_limit_fails() -> None:
    reference = {"a": result(-0.1, -0.1, 0.02)}
    candidate = {"a": result(-0.1, -0.1, 0.05)}
    report = compare(reference, candidate, [photo("a")])
    check = report["checks"]["max_margin_drift"]
    assert check["value"] == pytest.approx(0.03)
    assert check["limit"] == THRESHOLDS["limits"]["max_margin_drift"]
    assert check["passed"] is False
    assert report["passed"] is False


def test_a_near_tie_may_change_the_top_suggestion_but_a_clear_winner_may_not() -> None:
    reference = {"tie": result(0.050, 0.0, 0.049), "clear": result(0.10, 0.0, 0.0)}
    candidate = {"tie": result(0.049, 0.0, 0.050), "clear": result(0.0, 0.0, 0.10)}
    report = compare(reference, candidate, [photo("tie"), photo("clear")])
    changed = {row["photo_id"]: row for row in report["top_suggestion"]["changed"]}
    assert changed["tie"]["near_tie"] is True
    assert changed["clear"]["near_tie"] is False
    assert changed["clear"]["reference"] == CV
    assert changed["clear"]["candidate"] == UE
    assert report["checks"]["unexplained_top_changes"]["value"] == 1


def test_margin_zero_crossings_are_listed() -> None:
    reference = {"a": result(-0.1, -0.1, 0.004), "b": result(-0.1, -0.1, -0.3)}
    candidate = {"a": result(-0.1, -0.1, -0.003), "b": result(-0.1, -0.1, -0.3)}
    report = compare(reference, candidate, [photo("a"), photo("b")])
    assert report["margins"]["zero_crossings"] == ["a"]


def test_a_reference_photo_that_stops_finding_its_weed_fails() -> None:
    reference = {"r": result(-0.1, -0.1, 0.05)}
    candidate = {"r": result(-0.1, -0.1, -0.01)}
    photos = [photo("r", "reference", reference_species=UE)]
    report = compare(reference, candidate, photos)
    assert report["references"] == {"reference_found": 1, "candidate_found": 0, "lost": ["r"]}
    assert report["checks"]["references_lost"]["passed"] is False


def test_lookalikes_newly_passing_as_the_weed_fail() -> None:
    reference = {"toetoe": result(-0.1, -0.004, -0.2), "kanuka": result(-0.1, -0.1, 0.02)}
    candidate = {"toetoe": result(-0.1, 0.004, -0.2), "kanuka": result(-0.1, -0.1, 0.02)}
    photos = [
        photo("toetoe", "lookalike", lookalike_of=CS),
        photo("kanuka", "lookalike", lookalike_of=UE),
    ]
    report = compare(reference, candidate, photos)
    looks = report["lookalikes"]
    assert looks["reference"] == {"top": 2, "positive": 1, "of": 2}
    assert looks["candidate"] == {"top": 2, "positive": 2, "of": 2}
    assert looks["newly_positive"] == ["toetoe"]
    assert looks["newly_top"] == []
    assert report["checks"]["lookalikes_newly_positive"]["passed"] is False


def test_queue_change_counts_shared_photos_and_rank_shifts() -> None:
    first = [{"photo_id": pid} for pid in "abcdef"]
    second = [{"photo_id": pid} for pid in "fbcdea"]
    change = queue_change(first, second, 5)
    assert change == {
        "budget": 5,
        "shared": 4,
        "swaps": 1,
        "max_rank_shift": 5,
        "entered": ["f"],
        "left": ["a"],
    }


def test_queue_change_on_a_queue_shorter_than_the_budget() -> None:
    queue = [{"photo_id": "a"}, {"photo_id": "b"}]
    assert queue_change(queue, queue[::-1], 5)["swaps"] == 0


def test_more_than_one_swap_in_the_review_queue_fails() -> None:
    reference = incidental(6)
    candidate = dict(reference)
    # The two photos just outside the top 5 jump to the front.
    candidate["i05"] = result(-0.2, -0.2, 0.0)
    report = compare(reference, candidate, [photo(pid) for pid in reference], budgets=(5,))
    assert report["checks"]["incidental_queue_swaps"]["value"] == 1
    candidate["i04"], candidate["i03"] = result(-0.2, -0.2, -0.4), result(-0.2, -0.2, -0.5)
    report = compare(reference, candidate, [photo(pid) for pid in reference], budgets=(5,))
    assert report["checks"]["incidental_queue_swaps"]["value"] == 1  # only i05 is new
    candidate["i06"] = result(-0.2, -0.2, 0.01)
    reference["i06"] = result(-0.2, -0.2, -0.9)
    report = compare(reference, candidate, [photo(pid) for pid in reference], budgets=(5,))
    assert report["checks"]["incidental_queue_swaps"]["value"] == 2
    assert report["checks"]["incidental_queue_swaps"]["passed"] is False


def test_only_incidental_photos_are_in_the_review_queue() -> None:
    reference = incidental(3) | {"r": result(-0.1, -0.1, 0.5)}
    photos = [photo(pid) for pid in incidental(3)] + [photo("r", "reference", reference_species=UE)]
    report = compare(reference, reference, photos, budgets=(5,))
    assert report["queues"]["incidental"][0]["shared"] == 3
    assert report["queues"]["pooled"][0]["shared"] == 4


def test_thresholds_are_versioned_and_each_is_justified() -> None:
    assert isinstance(THRESHOLDS["version"], int)
    assert set(THRESHOLDS["limits"]) == set(THRESHOLDS["why"])
    assert all(len(reason) > 40 for reason in THRESHOLDS["why"].values())
    report = compare(incidental(1), incidental(1), [photo("i00")])
    assert report["thresholds"] == THRESHOLDS


def test_encoding_cost_reports_size_memory_and_per_photo_latency() -> None:
    cost = encoding_cost(
        artefact_bytes=300_000_000,
        peak_rss_bytes=900_000_000,
        baseline_rss_bytes=100_000_000,
        seconds=[0.2, 0.4, 0.3, 1.0],
        windows=[7, 7, 7, 33],
    )
    assert cost == {
        "artefact_mb": 300.0,
        "peak_rss_mb": 900.0,
        "peak_rss_above_baseline_mb": 800.0,
        "photos": 4,
        "seconds_per_photo": {"median": 0.35, "p90": 1.0, "mean": 0.475},
        "milliseconds_per_window": pytest.approx(1900 / 54, abs=0.05),
        "windows_per_photo_median": 7.0,
    }
