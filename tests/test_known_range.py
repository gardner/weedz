"""Known range helps reviewers prioritise but never ranks or hides a candidate (PRD P11)."""

import inspect
from typing import Any

from weedz.discovery.audit import queue_ranks
from weedz.discovery.inference import Screener


def candidate(pid: str, margin: float, comparison: dict[str, Any], **fields: Any) -> dict:
    return {
        "id": pid,
        "cohort": "incidental",
        "scores": {"best_species": "Ulex europaeus", "margin": margin},
        "latitude": -41.27,
        "longitude": 173.28,
        "reference_comparison": {"Ulex europaeus": comparison},
    } | fields


IN_RANGE = {"comparable": True, "within_radius": 40, "radius_m": 5000.0, "earliest_year": 1990}
OUT_OF_RANGE = {"comparable": True, "within_radius": 0, "radius_m": 5000.0}
UNCOMPARED = {"comparable": False, "reason": "Photo location is obscured or missing"}


def test_queue_order_ignores_reference_records_and_location() -> None:
    photos = [
        candidate("a", 0.05, IN_RANGE),
        candidate("b", 0.02, OUT_OF_RANGE),
        candidate("c", -0.01, UNCOMPARED),
    ]
    elsewhere = [
        candidate("a", 0.05, OUT_OF_RANGE, latitude=-46.4, longitude=168.3),
        candidate("b", 0.02, UNCOMPARED, latitude=None, longitude=None),
        candidate("c", -0.01, IN_RANGE),
    ]
    unloaded = [{k: v for k, v in p.items() if k != "reference_comparison"} for p in photos]
    assert queue_ranks(photos) == {"a": 1, "b": 2, "c": 3}
    assert queue_ranks(elsewhere) == queue_ranks(photos) == queue_ranks(unloaded)


def test_every_out_of_range_candidate_stays_in_the_queue() -> None:
    photos = [candidate(str(i), -0.5 + i / 10, OUT_OF_RANGE) for i in range(5)]
    assert set(queue_ranks(photos)) == {p["id"] for p in photos}


def test_screening_sees_only_the_image_and_its_original_subject() -> None:
    assert list(inspect.signature(Screener.screen).parameters) == ["self", "path", "subject"]
