"""Aggregation must preserve the declared budget without consulting source labels."""

import pytest
from pydantic import ValidationError

from weedz.species_aggregation import RankedTaxon, aggregate_taxa


def ranked(taxon: str, score: float) -> RankedTaxon:
    return RankedTaxon(taxon=taxon, score=score, score_kind="closed_set_softmax_uncalibrated")


def test_max_score_preserves_a_strong_rare_candidate_discarded_by_frequency() -> None:
    crops = [
        [ranked("rare", 0.9), ranked("common", 0.05)],
        [ranked("common", 0.4), ranked("other", 0.2)],
        [ranked("common", 0.3), ranked("other", 0.1)],
    ]
    assert aggregate_taxa(crops, policy="frequency", budget=1) == ["common"]
    assert aggregate_taxa(crops, policy="max_score", budget=1) == ["rare"]


@pytest.mark.parametrize("policy", ["frequency", "max_score"])
def test_unique_budgeted_output_and_stable_first_encounter_ties(policy: str) -> None:
    crops = [[ranked("b", 0.5), ranked("a", 0.5)], [ranked("a", 0.5), ranked("b", 0.5)]]
    assert aggregate_taxa(crops, policy=policy, budget=5) == ["b", "a"]
    assert aggregate_taxa(crops, policy=policy, budget=1) == ["b"]
    assert aggregate_taxa([], policy=policy, budget=5) == []


def test_repeated_taxon_within_one_crop_is_rejected() -> None:
    with pytest.raises(ValueError, match="Duplicate taxon"):
        aggregate_taxa([[ranked("a", 0.5), ranked("a", 0.4)]], policy="frequency", budget=5)


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -0.1, 1.1])
def test_invalid_softmax_scores_are_rejected(score: float) -> None:
    with pytest.raises(ValidationError):
        ranked("a", score)


def test_other_score_scales_are_rejected() -> None:
    with pytest.raises(ValidationError):
        RankedTaxon.model_validate({"taxon": "a", "score": 0.2, "score_kind": "margin"})


@pytest.mark.parametrize("budget", [0, -1, True])
def test_invalid_budgets_are_rejected(budget: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        aggregate_taxa([], policy="frequency", budget=budget)


def test_unknown_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        aggregate_taxa([], policy="typo", budget=5)
