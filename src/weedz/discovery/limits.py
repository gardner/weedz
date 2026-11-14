"""What a photo's location and dates can and cannot say about a plant (PRD P09).

A search area is centred on the observation point, where the photographer was, and is
never a plant point. Its radius is the reported positional accuracy plus a declared
allowance for the unknown camera-to-plant distance. Obscured, missing or unknown-accuracy
locations are not searchable, and no coordinates are invented for them. Capture, upload
and screening dates stay distinct, and a photo never asserts that a plant is there now.
"""

from collections import Counter
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel

# iNaturalist records no camera bearing, pose or focal distance, and hosted photos have
# their EXIF removed, so the distance from camera to a background plant is unknown. This
# is a declared planning allowance, not a measurement: a plant clear enough to identify
# in a hand-held photo is assumed to be within about 100 m of the camera. A telephoto
# background can be farther, so the area is where to start looking, not a bound.
CAMERA_TO_PLANT_ALLOWANCE_M = 100.0
ALLOWANCE_REASON = (
    f"{CAMERA_TO_PLANT_ALLOWANCE_M:g} m declared allowance for camera-to-plant distance: "
    "iNaturalist records no camera bearing or pose, so the plant may lie in any direction "
    "and, in a telephoto view, farther"
)
# docs/datasets.md (LINZ assessment): aerial imagery is site context only for leads
# with public coordinates accurate to about 20 m or better.
SITE_CONTEXT_ACCURACY_M = 20.0
CENTRE_IS = "observation point (where the photographer was), not a plant point"
NOT_SEARCHABLE = {
    "obscured": "Location obscured by the source; no search area without the true point",
    "missing": "No location supplied; no search area",
    "accuracy_unknown": "Location accuracy not supplied; the search radius cannot be stated",
}
SearchStatus = Literal["searchable", "obscured", "missing", "accuracy_unknown"]


class SearchArea(BaseModel):
    status: SearchStatus
    reason: str = ""
    centre: tuple[float, float] | None = None
    centre_is: str = CENTRE_IS
    accuracy_m: float | None = None
    allowance_m: float = CAMERA_TO_PLANT_ALLOWANCE_M
    allowance_reason: str = ALLOWANCE_REASON
    radius_m: float | None = None
    # Accurate enough for aerial imagery to show the site's context, never the plant.
    site_context: bool = False


class Dates(BaseModel):
    photographed: str | None
    uploaded: str | None
    screened: str | None
    days_photo_to_upload: int | None
    days_photo_to_screening: int | None
    current_presence: str


class Limits(BaseModel):
    search_area: SearchArea
    dates: Dates


def _status(photo: dict[str, Any]) -> SearchStatus:
    if photo.get("coordinate_status") == "obscured":
        return "obscured"
    located = photo.get("latitude") is not None and photo.get("longitude") is not None
    if photo.get("coordinate_status") != "public" or not located:
        return "missing"
    if photo.get("positional_accuracy_m") is None:
        return "accuracy_unknown"
    return "searchable"


def search_area(photo: dict[str, Any]) -> SearchArea:
    status = _status(photo)
    if status != "searchable":
        return SearchArea(status=status, reason=NOT_SEARCHABLE[status])
    accuracy = float(photo["positional_accuracy_m"])
    return SearchArea(
        status=status,
        centre=(photo["latitude"], photo["longitude"]),
        accuracy_m=accuracy,
        radius_m=accuracy + CAMERA_TO_PLANT_ALLOWANCE_M,
        site_context=accuracy <= SITE_CONTEXT_ACCURACY_M,
    )


def _day(value: str | None) -> date | None:
    return date.fromisoformat(value[:10]) if value else None


def _days(start: date | None, end: date | None) -> int | None:
    return (end - start).days if start and end else None


def _presence(photographed: date | None) -> str:
    if photographed is None:
        return (
            "Photo date unknown: even if the plant is visible, the photo cannot show "
            "when it was there, nor whether it is there now"
        )
    return (
        f"If the plant is visible, the photo shows it was there on {photographed.isoformat()}, "
        "not that it is there now"
    )


def limits(photo: dict[str, Any]) -> Limits:
    """The photo's search area and dates; it was screened when it was last scored."""
    photographed, uploaded = _day(photo.get("observed_on")), _day(photo.get("uploaded_at"))
    screened = _day(photo.get("screened_at"))
    return Limits(
        search_area=search_area(photo),
        dates=Dates(
            photographed=photographed.isoformat() if photographed else None,
            uploaded=uploaded.isoformat() if uploaded else None,
            screened=screened.isoformat() if screened else None,
            days_photo_to_upload=_days(photographed, uploaded),
            days_photo_to_screening=_days(photographed, screened),
            current_presence=_presence(photographed),
        ),
    )


def with_limits(photos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [photo | {"limits": limits(photo).model_dump(mode="json")} for photo in photos]


def search_area_summary(photos: list[dict[str, Any]]) -> dict[str, int]:
    """Distinct photos with a search area, how many are precise enough for site context,
    and the count of each reason the rest have none."""
    areas = [search_area(photo) for photo in {p["id"]: p for p in photos}.values()]
    reasons = Counter(area.status for area in areas if area.status != "searchable")
    return {
        "searchable": sum(area.status == "searchable" for area in areas),
        "site_context_precision": sum(area.site_context for area in areas),
    } | {status: reasons[status] for status in NOT_SEARCHABLE if reasons[status]}
