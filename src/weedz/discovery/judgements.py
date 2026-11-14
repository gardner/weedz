"""Separate judgements of identity, location usefulness, historical relevance and novelty.

Each judgement is one attributed answer on one dimension. They are kept apart from the
suggestion review so one can be settled while another is disputed or unassessed.
`unassessed` withdraws a reviewer's standing judgement on that dimension.
"""

from collections.abc import Callable
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from weedz.discovery.limits import search_area
from weedz.discovery.occurrences import predates
from weedz.discovery.records import ReviewerName

Dimension = Literal["identity", "location", "history", "novelty"]
JUDGEMENTS: dict[str, tuple[str, ...]] = {
    "identity": ("confirmed", "disputed", "unresolved", "unassessed"),
    "location": ("usable", "too_imprecise", "camera_point_only", "unknown", "unassessed"),
    "history": (
        "recent_evidence",
        "historical_evidence",
        "no_longer_present",
        "date_unknown",
        "unassessed",
    ),
    # Proportionate novelty (PRD P10), from weakest to strongest claim.
    "novelty": (
        "already_recorded",
        "new_in_photo",
        "absent_from_references",
        "earlier_than_records",
        "verified_new_locality",
        "unassessed",
    ),
}
# Claims that are only meaningful with the reviewer's reason.
NOTE_REQUIRED = {
    ("novelty", "verified_new_locality"): "A verified new locality needs the verification "
    "evidence in the note: who checked, how and when",
    ("identity", "unresolved"): "Say what additional evidence would resolve the identity",
    ("history", "no_longer_present"): "Say who reported the plant gone, and when",
}


class Judgement(BaseModel):
    # The recorded plant (a finding's id) being judged; None judges the suggested species.
    finding_id: int | None = None
    dimension: Dimension
    value: str
    reviewer: ReviewerName
    note: str = Field(default="", max_length=4000)
    effort_seconds: float | None = Field(default=None, ge=0, le=86_400)

    @model_validator(mode="after")
    def value_fits_dimension(self) -> "Judgement":
        if self.value not in JUDGEMENTS[self.dimension]:
            raise ValueError(
                f"{self.dimension} must be one of {', '.join(JUDGEMENTS[self.dimension])}"
            )
        reason = NOTE_REQUIRED.get((self.dimension, self.value))
        if reason and not self.note.strip():
            raise ValueError(reason)
        return self


def _located(photo: dict[str, Any], _taxon: str | None) -> bool:
    return search_area(photo).status == "searchable"


def _dated(photo: dict[str, Any], _taxon: str | None) -> bool:
    return bool(photo.get("observed_on"))


def _comparison(photo: dict[str, Any], taxon: str | None) -> dict[str, Any]:
    """The judged plant's comparison with the records, empty when it was not compared."""
    found = (photo.get("reference_comparison") or {}).get(taxon or "", {})
    return found if found.get("comparable") else {}


def _compared(photo: dict[str, Any], taxon: str | None) -> bool:
    return bool(_comparison(photo, taxon))


def _no_nearby_record(photo: dict[str, Any], taxon: str | None) -> bool:
    return _comparison(photo, taxon).get("within_radius") == 0


def _before_nearby_records(photo: dict[str, Any], taxon: str | None) -> bool:
    return predates(photo, _comparison(photo, taxon))


def judged_taxon(photo: dict[str, Any], finding_id: int | None) -> str | None:
    """The watchlist species a judgement is about; None for free text or no suggestion."""
    if finding_id is None:
        return photo["scores"].get("best_species")
    return next(
        (plant["species"] for plant in photo["findings"] if plant["id"] == finding_id), None
    )


Requirement = tuple[Callable[[dict[str, Any], str | None], bool], str]
UNDATED = "The photo date is unknown"
UNCOMPARED = (
    "No reference records were compared for this plant here, so novelty against records "
    "stays unassessed"
)
# What the photo, and its comparison for the judged plant, must offer before a claim.
PHOTO_REQUIREMENTS: dict[tuple[str, str], list[Requirement]] = {
    ("location", "usable"): [
        (_located, "The observation location is obscured, missing or of unknown accuracy")
    ],
    ("history", "recent_evidence"): [(_dated, UNDATED)],
    ("history", "historical_evidence"): [(_dated, UNDATED)],
    ("novelty", "absent_from_references"): [
        (_compared, UNCOMPARED),
        (_no_nearby_record, "A reference record of this species lies within the radius"),
    ],
    ("novelty", "earlier_than_records"): [
        (_dated, UNDATED),
        (_compared, UNCOMPARED),
        (
            _before_nearby_records,
            "The photo is not earlier than every dated record within the radius, or a "
            "record there is undated or none exists",
        ),
    ],
}


def unsupported(photo: dict[str, Any], record: Judgement) -> str | None:
    """Why the photo cannot support this judgement on its plant, or None. Needs the
    photo's reference comparisons; free-text taxa are never compared with records."""
    taxon = judged_taxon(photo, record.finding_id)
    for satisfied, reason in PHOTO_REQUIREMENTS.get((record.dimension, record.value), []):
        if not satisfied(photo, taxon):
            return reason
    return None


def no_judgements() -> dict[str, dict[str, dict]]:
    return {name: {} for name in JUDGEMENTS}


Target = tuple[str, int | None]


def standing_judgements(events: list[Any]) -> dict[Target, dict[str, dict[str, dict]]]:
    """Per judged plant (photo id and finding id, None for the suggestion) and dimension,
    each reviewer's latest judgement. Events are oldest first."""
    standing: dict[Target, dict[str, dict[str, dict]]] = {}
    for event in events:
        target = (event["photo_id"], event["finding_id"])
        by_dimension = standing.setdefault(target, no_judgements())
        by_reviewer = by_dimension[event["dimension"]]
        if event["value"] == "unassessed":
            by_reviewer.pop(event["reviewer"], None)
        else:
            by_reviewer[event["reviewer"]] = {
                "id": event["id"],
                "value": event["value"],
                "note": event["note"],
                "created_at": event["created_at"],
                "reference_snapshot": event["reference_snapshot"],
            }
    return standing


def judged(standing: dict[Target, dict[str, dict[str, dict]]], target: Target) -> dict:
    """A plant's standing judgements and the dimensions where reviewers disagree."""
    by_dimension = standing.get(target) or no_judgements()
    return {"judgements": by_dimension, "judgement_disputes": disputes(by_dimension)}


def disputes(standing: dict[str, dict[str, dict]]) -> list[str]:
    """Dimensions where reviewers' standing judgements differ."""
    return [
        name
        for name, by_reviewer in standing.items()
        if len({judgement["value"] for judgement in by_reviewer.values()}) > 1
    ]
