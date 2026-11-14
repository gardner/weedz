"""The corpus spreads across years, seasons and observers, reproducibly."""

from datetime import date

import pytest
from pydantic import ValidationError
from test_discovery import observation

from weedz.discovery.records import Photo, RunSpec
from weedz.discovery.sampling import coverage, season_windows, select_across_strata
from weedz.discovery.source import photo_from_observation


def candidate(obs_id: int, observed_on: str, observer: str = "ana") -> Photo:
    raw = observation() | {"id": obs_id, "observed_on": observed_on, "user": {"login": observer}}
    raw["photos"] = [raw["photos"][0] | {"id": obs_id * 10}]
    photo = photo_from_observation(raw, "Nelson", "incidental")
    assert photo is not None
    return photo


def test_season_windows_cover_the_period_in_southern_seasons() -> None:
    windows = season_windows(date(2023, 1, 1), date(2023, 12, 31))
    assert windows[0] == ("2023-DJF", date(2023, 1, 1), date(2023, 2, 28))
    assert ("2023-MAM", date(2023, 3, 1), date(2023, 5, 31)) in windows
    assert windows[-1] == ("2024-DJF", date(2023, 12, 1), date(2023, 12, 31))
    assert len(windows) == 5


def test_selection_rotates_through_strata_before_doubling_up() -> None:
    strata = {
        "2023-DJF": [candidate(1, "2023-01-05", "a"), candidate(2, "2023-01-06", "b")],
        "2023-JJA": [candidate(3, "2023-07-01", "c")],
        "2024-SON": [candidate(4, "2024-10-01", "d")],
    }
    chosen = select_across_strata(strata, 3)
    assert sorted(photo.observation_id for photo in chosen)[1:] == [3, 4]
    assert len({(photo.observed_on or "")[:7] for photo in chosen}) == 3


def test_selection_is_deterministic_and_order_independent() -> None:
    photos = [candidate(index, "2023-01-05", f"o{index}") for index in range(1, 30)]
    first = select_across_strata({"2023-DJF": photos}, 5)
    again = select_across_strata({"2023-DJF": list(reversed(photos))}, 5)
    assert [p.id for p in first] == [p.id for p in again]
    assert [p.id for p in first] != [p.id for p in photos[:5]]


def test_one_photo_per_observer_day_so_a_walk_cannot_dominate() -> None:
    walk = [candidate(index, "2024-12-30", "jenny") for index in range(1, 6)]
    other = [candidate(9, "2024-12-30", "sam"), candidate(10, "2024-12-31", "jenny")]
    chosen = select_across_strata({"2025-DJF": walk + other}, 5)
    assert len(chosen) == 3
    assert {(p.observer, p.observed_on) for p in chosen} == {
        ("jenny", "2024-12-30"),
        ("sam", "2024-12-30"),
        ("jenny", "2024-12-31"),
    }


def test_coverage_counts_years_seasons_and_observer_days() -> None:
    photos = [
        candidate(1, "2023-01-05", "a"),
        candidate(2, "2023-07-01", "a"),
        candidate(3, "2024-07-02", "b"),
    ]
    summary = coverage(photos, "stratified")
    assert summary["sampling"] == "stratified"
    assert summary["by_year"] == {"2023": 2, "2024": 1}
    assert summary["by_season"] == {"DJF": 1, "JJA": 2}
    assert (summary["observers"], summary["observer_days"]) == (2, 3)


def test_run_spec_defaults_to_stratified_and_rejects_an_empty_period() -> None:
    spec = RunSpec()
    assert (spec.sampling, spec.after) == ("stratified", date(2010, 1, 1))
    with pytest.raises(ValidationError):
        RunSpec(after=date(2024, 1, 1), before=date(2023, 1, 1))
