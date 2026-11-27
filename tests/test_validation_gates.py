"""Development-derived regression floors, never fitted to held-out successes."""

import pytest

from weedz.validation import metrics


@pytest.mark.parametrize(
    "successes,total,held_out_total,higher,expected",
    [
        (80, 100, 200, True, 0.655969246),
        (20, 100, 200, False, 0.344030754),
        (0, 10, 10, True, 0.0),
        (10, 10, 10, False, 1.0),
        # p_d=.7, n_h=13: use round(9.1)=9, not the fractional expected successes.
        (7, 10, 13, True, 0.172028382),
    ],
)
def test_floor_matches_hand_calculated_wilson_bounds(
    successes: int, total: int, held_out_total: int, higher: bool, expected: float
):
    assert metrics.development_floor(successes, total, held_out_total, higher) == pytest.approx(
        expected, abs=1e-8
    )


@pytest.mark.parametrize("higher,successes", [(True, 80), (False, 20)])
def test_matching_held_out_sample_clears_the_whole_interval(higher: bool, successes: int):
    bound = metrics.development_floor(successes, 100, 200, higher)
    measured = metrics.rate(
        "recall" if higher else "false_alarm_rate",
        successes * 2,
        200,
        target=bound if higher else None,
        ceiling=None if higher else bound,
    )
    assert measured.passed is True


@pytest.mark.parametrize("counts", [(0, 0, 20), (0, 20, 0)])
def test_missing_development_or_held_out_trials_cannot_establish_a_gate(
    counts: tuple[int, int, int],
):
    assert metrics.development_floor(*counts, True) is None


@pytest.mark.parametrize("counts", [(-1, 10, 10), (11, 10, 10), (0, -1, 10), (0, 10, -1)])
def test_invalid_floor_counts_are_rejected(counts: tuple[int, int, int]):
    with pytest.raises(ValueError, match="counts"):
        metrics.development_floor(*counts, True)


def test_cohort_hash_is_order_independent_and_binds_strata():
    from weedz.validation.gates import cohort_sha256

    assert cohort_sha256([("a", "dev"), ("b", "held")]) == cohort_sha256(
        [("b", "held"), ("a", "dev")]
    )
    assert cohort_sha256([("a", "dev")]) != cohort_sha256([("a", "held")])


def test_gate_uses_development_counts_and_only_the_requested_held_out_stratum():
    from weedz.validation.gates import apply_development_gates

    config = {}
    limits = []
    rows = [
        metrics.rate("recall", s, n, stratum=g)
        for g, s, n in [("all", 180, 300), ("development", 80, 100), ("held-out", 100, 200)]
    ]
    gated = apply_development_gates(
        rows,
        [rows[1]],
        ("recall",),
        config,
        limits,
        development_stratum="development",
        held_out_stratum="held-out",
    )
    assert gated[0] == rows[0] and gated[1] == rows[1]
    assert gated[2].target == metrics.development_floor(80, 100, 200, True)
    assert gated[2].passed is False
    assert config["gate_development_recall"] == "80/100"
    assert not limits


def test_missing_development_is_ungated_with_explicit_reason():
    from weedz.validation.gates import apply_development_gates

    config = {}
    limits = []
    rows = [metrics.rate("recall", 5, 10)]
    assert apply_development_gates(rows, [], ("recall",), config, limits) == rows
    assert config["gate_development_recall"] == "0/0"
    assert "recall" in limits[0] and "development" in limits[0]


def test_hash_split_rows_preserve_all_and_score_each_id_in_exactly_one_half():
    from weedz.validation.gates import hash_split_metrics
    from weedz.validation.splits import split_of

    items = [(str(i), i < 5) for i in range(10)]

    def score(members):
        return [metrics.rate("recall", sum(hit for _, hit in members), len(members))]

    rows = hash_split_metrics(items, score, lambda item: item[0])
    assert rows[0] == score(items)[0]
    for split in ("development", "held-out"):
        row = next(row for row in rows if row.stratum == split)
        members = [item for item in items if split_of(item[0]) == split]
        assert (row.successes, row.total) == (sum(hit for _, hit in members), len(members))
