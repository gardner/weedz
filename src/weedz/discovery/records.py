"""Serializable records shared by activities, API and saved run manifests."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

REGIONS = {"Nelson": 40493, "Tasman": 40494}
SPECIES = {
    "Clematis vitalba": "Old man's beard",
    "Cortaderia selloana": "Pampas grass",
    "Ulex europaeus": "Gorse",
}
TASK_QUEUE = "weedz-discovery-v1"
ReviewStatus = Literal["unreviewed", "confirmed", "rejected", "uncertain"]


class RunSpec(BaseModel):
    limit_per_region: int = Field(default=12, ge=1, le=50)
    controls_per_species: int = Field(default=1, ge=0, le=3)
    before: date = date(2024, 12, 31)


class Photo(BaseModel):
    id: str
    observation_id: int
    photo_id: int
    region: str
    cohort: Literal["incidental", "reference"]
    reference_species: str | None = None
    source_url: str
    image_url: str
    attribution: str
    photo_license: str
    observation_license: str
    observer: str
    original_taxon: str
    original_common_name: str
    observed_on: str | None = None
    uploaded_at: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    positional_accuracy_m: float | None = None
    coordinate_status: Literal["public", "obscured", "missing"]
    image_path: str = ""
    sha256: str = ""


ReviewerName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class Review(BaseModel):
    status: ReviewStatus
    # Attribution on a local stack, not authentication; see issue #31 for remote review.
    reviewer: ReviewerName
    note: str = Field(default="", max_length=4000)
    # Active, visible time on this photo measured by the review app; None when not measured.
    effort_seconds: float | None = Field(default=None, ge=0, le=86_400)
