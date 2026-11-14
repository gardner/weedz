"""The outcomes report states how many leads could be searched for, and why others cannot."""

from test_outcomes import export, measure, photo

from weedz.discovery.outcome_report import to_markdown
from weedz.discovery.outcomes import outcomes


def test_completeness_counts_photos_by_search_area() -> None:
    photos = [
        photo("a", "a"),
        photo("b", positional_accuracy_m=300.0),
        photo("c", coordinate_status="obscured"),
        photo("d", positional_accuracy_m=None),
    ]
    complete = measure(outcomes(export(photos)), "evidence_completeness")
    assert complete["evidence"]["missing"] == {"location": 2}
    assert complete["evidence"]["search_areas"] == {
        "searchable": 2,
        "site_context_precision": 1,
        "obscured": 1,
        "accuracy_unknown": 1,
    }


def test_a_public_point_without_coordinates_is_not_a_complete_location() -> None:
    complete = measure(outcomes(export([photo("a", latitude=None)])), "evidence_completeness")
    assert complete["evidence"]["missing"] == {"location": 1}


def test_follow_up_states_which_watchlist_findings_have_a_search_area() -> None:
    """Counted per photo: a photo with two watchlist plants has one search area."""
    photos = [
        photo(
            "a",
            "a",
            review_status="confirmed",
            findings=[{"id": 1, "kind": "addition", "species": "Ulex europaeus"}],
        ),
        photo("b", "b", review_status="confirmed", coordinate_status="obscured"),
        photo("c", "c"),
    ]
    follow_up = measure(outcomes(export(photos)), "follow_up_usefulness")
    assert follow_up["value"] is None
    assert follow_up["evidence"]["watchlist_finding_search_areas"] == {
        "searchable": 1,
        "site_context_precision": 1,
        "obscured": 1,
    }
    assert "watchlist_finding_search_areas: searchable: 1" in to_markdown(outcomes(export(photos)))
