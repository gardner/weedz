"""Serializable records shared by activities, API and saved run manifests."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

REGIONS = {"Nelson": 40493, "Tasman": 40494}
SPECIES = {
    "Clematis vitalba": "Old man's beard",
    "Cortaderia selloana": "Pampas grass",
    "Ulex europaeus": "Gorse",
}
TASK_QUEUE = "weedz-discovery-v1"
# Stratified runs span 2008 to today at most, bounding them to four season queries a year.
INATURALIST_FOUNDED = date(2008, 1, 1)
ReviewStatus = Literal["unreviewed", "confirmed", "rejected", "uncertain"]


class RunSpec(BaseModel):
    limit_per_region: int = Field(default=12, ge=1, le=50)
    controls_per_species: int = Field(default=1, ge=0, le=3)
    before: date = date(2024, 12, 31)
    # A key of weedz.discovery.inference.MODELS; see issue #14.
    model: Literal["bioclip", "bioclip-2"] = "bioclip"
    after: date = date(2010, 1, 1)
    # "recent" reproduces the first pilot's newest-first selection; see issue #5.
    sampling: Literal["stratified", "recent"] = "stratified"

    @classmethod
    def from_saved(cls, saved: dict) -> "RunSpec":
        """Runs saved before stratified sampling existed were newest-first runs."""
        return cls.model_validate({"sampling": "recent"} | saved)

    @model_validator(mode="after")
    def stratified_period_is_bounded(self) -> "RunSpec":
        """Only stratified runs query by period; recent runs ignore `after`."""
        if self.sampling != "stratified":
            return self
        if self.after < INATURALIST_FOUNDED:
            raise ValueError("The sampling period cannot start before iNaturalist (2008)")
        if self.after > self.before:
            raise ValueError("The sampling period must start on or before its end")
        if self.before > date.today():
            raise ValueError("The sampling period cannot end in the future")
        return self


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


class Audit(BaseModel):
    """A blind answer to "Is any watchlist weed visible?" for an audit-sample photo."""

    finding: str
    reviewer: ReviewerName
    note: str = Field(default="", max_length=4000)
    effort_seconds: float | None = Field(default=None, ge=0, le=86_400)

    @field_validator("finding")
    @classmethod
    def known_finding(cls, value: str) -> str:
        if value not in {*SPECIES, "none", "unsure"}:
            raise ValueError("Finding must be a watchlist species, 'none' or 'unsure'")
        return value
