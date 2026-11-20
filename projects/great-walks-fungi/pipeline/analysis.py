"""Geographic admission and observation seasonality; never abundance estimates."""

from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any

from pyproj import Transformer
from shapely import transform
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

TO_METRES = Transformer.from_crs(4326, 2193, always_xy=True)
TO_DEGREES = Transformer.from_crs(2193, 4326, always_xy=True)


@dataclass(frozen=True)
class RouteArea:
    route: BaseGeometry
    area: BaseGeometry

    def covers_location(self, location: str) -> bool:
        latitude, longitude = (float(v) for v in location.split(","))
        return self.area.covers(Point(*TO_METRES.transform(longitude, latitude)))

    def bounds(self) -> tuple[float, float, float, float]:
        return transform(self.area, TO_DEGREES.transform, interleaved=False).bounds


def route_area(route: BaseGeometry, radius_km: float) -> RouteArea:
    if not 0 < radius_km <= 50 or route.is_empty:
        raise ValueError("Use a nonempty route and a buffer between 0 and 50 km")
    projected = transform(route, TO_METRES.transform, interleaved=False)
    return RouteArea(projected, projected.buffer(radius_km * 1000))


def admit(record: dict[str, Any], first_year: int, last_year: int) -> str | None:
    """Return an exclusion reason, or None for a dated, openly located record."""
    try:
        observed = date.fromisoformat(record.get("observed_on") or "")
    except (ValueError, TypeError):
        return "missing_or_invalid_observation_date"
    if not first_year <= observed.year <= last_year:
        return "outside_complete_year_window"
    if record.get("obscured") or any(
        record.get(field) not in (None, "open") for field in ("geoprivacy", "taxon_geoprivacy")
    ):
        return "private_or_obscured_location"
    accuracy = record.get("positional_accuracy")
    if accuracy is None or not isinstance(accuracy, (float, int)) or not 0 <= accuracy <= 1000:
        return "unknown_or_over_1000m_accuracy"
    try:
        lat, lon = (float(v) for v in str(record.get("location")).split(","))
        if not (-48 <= lat <= -33 and 165 <= lon <= 180):
            return "outside_main_nz_islands"
    except (ValueError, TypeError):
        return "invalid_location"
    return None


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Count unique observation IDs and unique observer-days in each recorded month."""
    unique = {r["id"]: r for r in records}
    counts: Counter[int] = Counter()
    observer_days: dict[int, set[tuple[int, str]]] = {m: set() for m in range(1, 13)}
    years: Counter[int] = Counter()
    for record in unique.values():
        observed = date.fromisoformat(record["observed_on"])
        counts[observed.month] += 1
        years[observed.year] += 1
        observer_days[observed.month].add((record["user"]["id"], record["observed_on"]))
    values = [counts[m] for m in range(1, 13)]
    peak = max(values)
    return {
        "total": len(unique),
        "counts": values,
        "observer_days": [len(observer_days[m]) for m in range(1, 13)],
        "peak_months": [m for m in range(1, 13) if peak and counts[m] == peak],
        "years": sorted(years),
        "year_counts": dict(sorted(years.items())),
        "duplicate_records_removed": len(records) - len(unique),
    }
