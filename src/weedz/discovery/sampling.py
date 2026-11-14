"""Spread an incidental corpus across years, seasons and observers, reproducibly.

Candidates come from one query per southern-hemisphere season, so no single week or
walk dominates. Order within a season comes from a stable hash of the observation id,
so the same snapshots always give the same selection without unseeded API randomness.
"""

import calendar
import hashlib
from collections import Counter
from collections.abc import Iterable
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


def _spread(count: int) -> list[int]:
    """Indices 0..count-1 in bit-reversed (van der Corput) order: 0, 8, 4, 12, 2, ...

    Every prefix is spread evenly over the whole range, so a short sample already
    reaches both ends and the middle of a long period.
    """
    bits = max(1, (count - 1).bit_length())
    reversed_bits = (int(f"{index:0{bits}b}"[::-1], 2) for index in range(1 << bits))
    return [index for index in reversed_bits if index < count]


def _stratum_order(keys: list[str]) -> list[str]:
    """Order "YEAR-SEASON" strata so every prefix spans the period and the seasons.

    Each round visits every year once, in spread order, giving each year a different
    season. The shift by `rank // 4` stops seasons tracking a quarter of the period,
    and four rounds visit every year x season cell exactly once.
    """
    years = sorted({key.split("-")[0] for key in keys})
    seasons = list(SEASONS)
    order = {
        f"{years[index]}-{seasons[(rank + rank // 4 + round_) % 4]}": (round_, rank)
        for round_ in range(len(seasons))
        for rank, index in enumerate(_spread(len(years)))
    }
    return sorted(keys, key=lambda key: order.get(key, (len(seasons), 0)))


def select_across_strata(
    strata: dict[str, list[Photo]], limit: int, taken: Iterable[Photo] = ()
) -> list[Photo]:
    """Round-robin across strata, at most one photo per observer per day.

    Observer-days already used by `taken` (such as another region's sample) stay used.
    """
    queues = {key: sorted(strata[key], key=_stable) for key in _stratum_order(list(strata))}
    chosen: list[Photo] = []
    visits = {(photo.observer, photo.observed_on) for photo in taken}
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
