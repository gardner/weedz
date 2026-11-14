"""A discovery study's definition (PRD P01, Journey 1): what it asks, for whom, its bounds
and why, its review budget, its reference records and its agreed success limits.

A study records decisions; it never makes them. Whatever is not recorded stays an open
decision, and a success limit not agreed gives no verdict. The screening's regions,
watchlist and lookalikes are code constants (`records.py`, `lookalikes.py`): a study
names them with its rationale, must mark anything else "not yet screened", and every
difference from the code is listed rather than hidden.
"""

from datetime import date
from typing import Annotated, Any, Literal, NamedTuple

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    model_validator,
)

from weedz.discovery.lookalikes import LOOKALIKES
from weedz.discovery.outcome_terms import CONDITIONS
from weedz.discovery.records import REGIONS, SPECIES, ReviewerName, RunSpec


def _one_line(value: str) -> str:
    if "\n" in value or "\r" in value:
        raise ValueError("Keep this to one line; the review app edits it as one")
    return value


def _no_colon(value: str) -> str:
    if ":" in value:
        raise ValueError(f"{value!r}: a name cannot contain ':', which the review app's lists use")
    return value


# Longer prose may span lines; names and short notes are edited in the review app as
# single lines, and lists as "Name: why" lines, so they must round-trip unchanged.
Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Line = Annotated[Text, AfterValidator(_one_line)]
Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=200),
    AfterValidator(_one_line),
    AfterValidator(_no_colon),
]
Direction = Literal["at least", "at most"]


class LimitTerms(NamedTuple):
    """How an outcome measure's agreed limit reads: its measure, direction and unit."""

    measure: str
    direction: Direction
    unit: str

    @property
    def percent(self) -> bool:
        return self.unit.startswith("%")


_TERMS: dict[str, tuple[Direction, str]] = {
    "useful_incidental_yield": ("at least", "independent site visits with a useful finding"),
    "reviewer_effort_per_useful_finding": ("at most", "review minutes per useful finding"),
    "missed_visible_targets": ("at most", "% of audited photos with a missed visible target"),
    "novel_or_earlier_evidence": ("at least", "findings with defensible novel or earlier evidence"),
    "false_alarm_workload": ("at most", "review minutes on false alarms"),
    "follow_up_usefulness": ("at least", "% of shared leads that support a next step"),
    "evidence_completeness": ("at least", "% of incidental photos with complete evidence"),
    "coverage": ("at least", "% of incidental photos reviewed"),
}
LIMITS = {key: LimitTerms(CONDITIONS[key][0], *terms) for key, terms in _TERMS.items()}
TABLES = """
CREATE TABLE IF NOT EXISTS study_versions (
    study_id TEXT NOT NULL, version INTEGER NOT NULL, definition TEXT NOT NULL,
    author TEXT NOT NULL, change_note TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(study_id, version)
);
CREATE TABLE IF NOT EXISTS run_studies (
    id INTEGER PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
    study_id TEXT NOT NULL, linked_by TEXT NOT NULL, created_at TEXT NOT NULL
);
"""
LOOKALIKE_NAMES = {item["name"]: item["confusable_with"] for item in LOOKALIKES.values()}


class Person(BaseModel):
    role: Name
    name: Name


class Area(BaseModel):
    name: Name
    rationale: Line = ""
    screened: bool = True


class WatchSpecies(BaseModel):
    species: Name
    rationale: Line = ""
    screened: bool = True


class LookalikeNote(BaseModel):
    taxon: Name
    rationale: Line = ""
    screened: bool = True


class ReferenceRecords(BaseModel):
    name: Name
    note: Line = ""


class Budget(BaseModel):
    hours: float | None = Field(default=None, gt=0, le=100_000)
    photos: int | None = Field(default=None, gt=0, le=1_000_000)
    note: Line = ""


class Limit(BaseModel):
    value: float = Field(ge=0, le=1_000_000)
    note: Line = ""


def _check_in_code(names: list[tuple[str, bool]], known: set[str], what: str, mark: str) -> None:
    """Each name once; a name the screening covers is screened, any other is marked."""
    seen: set[str] = set()
    for name, screened in names:
        if name in seen:
            raise ValueError(f"{name} appears more than once")
        seen.add(name)
        if screened and name not in known:
            raise ValueError(f"{name} is {what}; mark it {mark}")
        if not screened and name in known:
            raise ValueError(f"{name} is screened; do not mark it {mark}")


class StudyDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["provisional", "agreed"] = "provisional"
    question: Text = ""
    partner: Line = ""
    people: list[Person] = Field(default_factory=list, max_length=50)
    regions: list[Area] = Field(default_factory=list, max_length=20)
    period_start: date | None = None
    period_end: date | None = None
    period_rationale: Text = ""
    watchlist: list[WatchSpecies] = Field(default_factory=list, max_length=50)
    lookalikes: list[LookalikeNote] = Field(default_factory=list, max_length=50)
    source_collection: Text = ""
    subject_selection: Text = ""
    review_budget: Budget = Field(default_factory=Budget)
    reference_records: list[ReferenceRecords] = Field(default_factory=list, max_length=20)
    limits: dict[str, Limit] = Field(default_factory=dict)

    @model_validator(mode="after")
    def consistent(self, info: ValidationInfo) -> "StudyDefinition":
        if self.status == "agreed" and not (self.question and self.partner):
            raise ValueError("An agreed study needs a question and a partner")
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("The study period must start on or before its end")
        # A stored version was checked when recorded; the code may have changed since,
        # and `differences` then names what it no longer covers.
        if not (info.context or {}).get("stored"):
            self._check_against_code()
        return self

    def _check_against_code(self) -> None:
        mark = "not yet screened (screened: false)"
        regions = [(item.name, item.screened) for item in self.regions]
        _check_in_code(regions, set(REGIONS), "not a screened region", mark)
        species = [(item.species, item.screened) for item in self.watchlist]
        _check_in_code(species, set(SPECIES), "not in the screening watchlist", mark)
        taxa = [(item.taxon, item.screened) for item in self.lookalikes]
        _check_in_code(taxa, set(LOOKALIKE_NAMES), "not a declared lookalike", mark)
        for key, limit in self.limits.items():
            if key not in LIMITS:
                raise ValueError(f"Unknown outcome measure {key!r}")
            if LIMITS[key].percent and limit.value > 100:
                raise ValueError(f"The {key} limit is a percentage, at most 100")

    @classmethod
    def stored(cls, data: dict[str, Any]) -> "StudyDefinition":
        """A recorded version, read whatever the screening code covers now."""
        return cls.model_validate(data, context={"stored": True})


class StudyEdit(BaseModel):
    """A new version of a study: the whole definition, who made it, and the version it
    replaces (0 for a new study), so two people cannot silently overwrite each other."""

    definition: StudyDefinition
    author: ReviewerName
    base_version: int = Field(default=0, ge=0)
    change_note: Line = ""


class NewStudy(StudyEdit):
    """A new study, linked to `run_id` by its author when one is given."""

    run_id: Name | None = None


class StudyLink(BaseModel):
    study_id: Name
    linked_by: ReviewerName


def terms() -> dict[str, Any]:
    """What the screening code covers, and how each limit reads, for a study to name."""
    return {
        "regions": list(REGIONS),
        "species": SPECIES,
        "lookalikes": [
            {"name": name, "confusable_with": weed} for name, weed in LOOKALIKE_NAMES.items()
        ],
        "limits": {key: item._asdict() for key, item in LIMITS.items()},
    }


def open_decisions(study: StudyDefinition) -> list[str]:
    """What the study has not recorded yet, so it is never mistaken for agreed."""
    budget = study.review_budget
    recorded = {
        "Discovery question": study.question,
        "Partner": study.partner,
        "Responsible people": study.people,
        "Regions": study.regions,
        "Historical period": study.period_start or study.period_end,
        "Watchlist": study.watchlist,
        "Source collection": study.source_collection,
        "Original-subject selection": study.subject_selection,
        "Review budget": budget.hours or budget.photos,
        "Reference records": study.reference_records,
    }
    decisions = [name for name, value in recorded.items() if not value]
    return decisions + [
        f"Success limit: {terms.measure}"
        for key, terms in LIMITS.items()
        if key not in study.limits
    ]


def _no_longer(names: list[tuple[str, bool]], known: set[str]) -> list[str]:
    return [
        f"{name} was screened when recorded, but the screening no longer covers it"
        for name, screened in names
        if screened and name not in known
    ]


def _screening_gaps(study: StudyDefinition) -> list[str]:
    watched = {item.species for item in study.watchlist}
    explained = {item.taxon for item in study.lookalikes if item.rationale}
    regions = {item.name for item in study.regions}
    notes = [
        f"{name} is screened by every run but not in this study's watchlist"
        for name in SPECIES
        if name not in watched
    ]
    notes += _no_longer([(item.species, item.screened) for item in study.watchlist], set(SPECIES))
    notes += _no_longer([(item.name, item.screened) for item in study.regions], set(REGIONS))
    notes += _no_longer(
        [(item.taxon, item.screened) for item in study.lookalikes], set(LOOKALIKE_NAMES)
    )
    notes += [
        f"{item.species} is in the watchlist but not yet screened"
        for item in study.watchlist
        if not item.screened
    ]
    notes += [
        f"{name} is queried by every run but not one of this study's regions"
        for name in REGIONS
        if name not in regions
    ]
    notes += [
        f"{item.taxon} is a lookalike but not yet screened"
        for item in study.lookalikes
        if not item.screened
    ]
    notes += [
        f"{item.name} is a study region but not yet screened"
        for item in study.regions
        if not item.screened
    ]
    notes += [
        f"{name} is a declared lookalike of {weed} with no rationale in this study"
        for name, weed in LOOKALIKE_NAMES.items()
        if weed in watched and name not in explained
    ]
    return notes


def differences(study: StudyDefinition, spec: RunSpec | None) -> list[str]:
    """Every way the study differs from what the screening code, and the run, cover."""
    notes = _screening_gaps(study)
    if spec is None or spec.sampling != "stratified":
        return notes
    start, end = study.period_start, study.period_end
    if (start and spec.after < start) or (end and spec.before > end):
        notes.append(
            f"The run's period {spec.after} to {spec.before} reaches outside the study "
            f"period {start or 'open'} to {end or 'open'}"
        )
    return notes


def _use(budget: float | None, used: float, lower_bound: bool) -> dict[str, Any]:
    if budget is None:
        state = "not set"
    elif used >= budget:
        state = "spent"
    else:
        state = "within so far" if lower_bound else "within"
    return {"budget": budget, "used": used, "lower_bound": lower_bound, "state": state}


def budget_use(budget: Budget, minutes: float, untimed: int, photos: int) -> dict[str, Any]:
    """Measured review hours and reviewed photos against the budget. Untimed work makes
    the hours a lower bound: spent is certain, within is only so far."""
    return {
        "hours": _use(budget.hours, round(minutes / 60, 2), untimed > 0),
        "photos": _use(budget.photos, photos, False),
        "note": budget.note,
    }
