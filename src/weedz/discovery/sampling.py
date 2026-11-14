"""Spread an incidental corpus across years, seasons and observers, reproducibly.

Candidates come from one query per southern-hemisphere season, so no single week or
walk dominates. Order within a season comes from a stable hash of the observation id,
so the same snapshots always give the same selection without unseeded API randomness.
"""

import calendar
import hashlib
from collections import Counter
from datetime import date
from typing import Any

from weedz.discovery.records import Photo

# Southern-hemisphere seasons; December belongs to the following year's summer.
SEASONS = {"DJF": (12, 2), "MAM": (3, 5), "JJA": (6, 8), "SON": (9, 11)}


def season_of(month: int) -> str:
    return next(
        name
        for name, (start, end) in SEASONS.items()
        if (start <= month <= end) or (start > end and (month >= start or month <= end))
    )


def season_windows(after: date, before: date) -> list[tuple[str, date, date]]:
    """Each (season label, first day, last day) overlapping the period, clipped to it."""
    windows = []
    for year in range(after.year, before.year + 2):
        for name, (start, end) in SEASONS.items():
            first = date(year - 1 if start > end else year, start, 1)
            last = date(year, end, calendar.monthrange(year, end)[1])
            if last >= after and first <= before:
                windows.append((f"{year}-{name}", max(first, after), min(last, before)))
    return windows


def _stable(photo: Photo) -> bytes:
    return hashlib.sha256(f"weedz-sample-v1|{photo.observation_id}".encode()).digest()


def _diagonal(keys: list[str]) -> list[str]:
    """Order "YEAR-SEASON" strata so consecutive picks change both year and season.

    Walking diagonals of the year x season grid means the first few picks already span
    several years and every season, instead of exhausting the earliest year first.
    """
    years = sorted({key.split("-")[0] for key in keys})
    order = {
        f"{years[(diagonal + index) % len(years)]}-{season}": (diagonal, index)
        for diagonal in range(len(years))
        for index, season in enumerate(SEASONS)
    }
    return sorted(keys, key=lambda key: order.get(key, (len(years), 0)))


def select_across_strata(strata: dict[str, list[Photo]], limit: int) -> list[Photo]:
    """Round-robin across strata, at most one photo per observer per day."""
    queues = {key: sorted(strata[key], key=_stable) for key in _diagonal(list(strata))}
    chosen: list[Photo] = []
    visits: set[tuple[str, str | None]] = set()
    while len(chosen) < limit and any(queues.values()):
        for queue in queues.values():
            while queue:
                photo = queue.pop(0)
                visit = (photo.observer, photo.observed_on)
                if visit not in visits:
                    visits.add(visit)
                    chosen.append(photo)
                    break
            if len(chosen) == limit:
                break
    return chosen


def coverage(photos: list[Photo], sampling: str) -> dict[str, Any]:
    dated = [photo.observed_on for photo in photos if photo.observed_on]
    return {
        "sampling": sampling,
        "photos": len(photos),
        "by_year": dict(sorted(Counter(day[:4] for day in dated).items())),
        "by_season": dict(sorted(Counter(season_of(int(day[5:7])) for day in dated).items())),
        "undated": len(photos) - len(dated),
        "observers": len({photo.observer for photo in photos}),
        "observer_days": len({(photo.observer, photo.observed_on) for photo in photos}),
    }
