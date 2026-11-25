"""Only matching independent review accounts support blind outcome comparisons."""

import pytest

from weedz.annotation.pilot_outcomes import evaluate_blind

GORSE = "Ulex europaeus"
PAMPAS = "Cortaderia selloana"


def task(key: str) -> dict:
    return {"data": {"image": key}, "meta": {"external_id": key, "image_sha256": key * 64}}


def result(name: str, *choices: str) -> dict:
    return {"from_name": name, "to_name": "image", "type": "choices", "value": {"choices": choices}}


def vote(reviewer: int, *taxa: str, status: str = "Watchlist plant visible") -> dict:
    results = [result("watchlist_presence", status)]
    if taxa:
        results.append(result("watchlist_species", *taxa))
    for row in results:
        row["value"]["choices"] = list(row["value"]["choices"])
    return {
        "completed_by": reviewer,
        "was_cancelled": False,
        "result": results,
    }


def exported(key: str, *votes: dict) -> dict:
    return task(key) | {
        "id": 7,
        "annotations": [v | {"id": i, "task": 7} for i, v in enumerate(votes, 1)],
    }


def seal(key: str, target: str | None) -> dict:
    row = task(key)["meta"]
    return row | {"target": target}


def test_agreed_visible_taxa_expose_misses_and_unsupported_suggestions() -> None:
    votes = [vote(1, GORSE), vote(2, GORSE)]
    summary = evaluate_blind([task("a")], [exported("a", *votes)], [seal("a", PAMPAS)])
    assert summary["consensus"] == {"agreed_visible": 1}
    assert summary["agreed_visible_taxa"] == 1
    assert summary["agreed_taxa_missed"] == 1
    assert summary["suggestions_supported"] == 0
    assert summary["suggestions_unsupported"] == 1


def test_single_reviewer_duplicate_rows_cannot_become_independent_consensus() -> None:
    votes = [vote(1, GORSE), vote(1, GORSE)]
    summary = evaluate_blind([task("a")], [exported("a", *votes)], [seal("a", None)])
    assert summary["consensus"] == {"single_reviewer": 1}
    assert summary["agreed_taxa_missed"] == 0


def test_disagreement_and_unsure_stay_out_of_agreed_denominators() -> None:
    votes = [vote(1, GORSE), vote(2, PAMPAS)]
    summary = evaluate_blind([task("a")], [exported("a", *votes)], [seal("a", GORSE)])
    assert summary["consensus"] == {"disagreement": 1}
    assert summary["suggestions_unassessed"] == 1
    votes = [vote(1, GORSE), vote(2, status="Unsure")]
    summary = evaluate_blind([task("a")], [exported("a", *votes)], [seal("a", GORSE)])
    assert summary["consensus"] == {"uncertain": 1}
    assert summary["agreed_visible_taxa"] == 0


def test_empty_export_and_seal_binding() -> None:
    summary = evaluate_blind([task("a")], [], [seal("a", None)])
    assert summary["consensus"] == {"unreviewed": 1}
    with pytest.raises(ValueError, match="sealed decisions"):
        evaluate_blind([task("a")], [], [seal("b", None)])


def test_agreed_absence_counts_only_explicit_answers() -> None:
    votes = [vote(i, status="No watchlist plant visible") for i in (1, 2)]
    summary = evaluate_blind([task("a")], [exported("a", *votes)], [seal("a", PAMPAS)])
    assert summary["consensus"] == {"agreed_no_visible": 1}
    assert summary["suggestions_unsupported"] == 1


def test_visible_answer_without_species_is_uncertain() -> None:
    summary = evaluate_blind(
        [task("a")], [exported("a", vote(1), vote(2, GORSE))], [seal("a", GORSE)]
    )
    assert summary["consensus"] == {"uncertain": 1}
    assert summary["suggestions_unassessed"] == 1
