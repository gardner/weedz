"""Whether a run's photo collection suits the study, before anyone reviews it (PRD P02, P14).

One summary of the incidental photos' dates, locations, permitted uses, missing
information, independence, screening and comparison basis, and of which photos cannot
support which conclusions. Each part is read from what the run export already
computes (limits, sharing, site-visit groups, corpus coverage, reference comparison,
the study), never re-derived. Counts are photos with their independent site visits and
ungrouped photos. Unknown stays unknown, and an unassessed photo, area or year is
never presented as weed-free.
"""

import calendar
import statistics
from collections import Counter
from collections.abc import Callable
from datetime import date
from typing import Any

from weedz.discovery.limits import (
    NOT_SEARCHABLE,
    SITE_CONTEXT_ACCURACY_M,
    calendar_day,
    search_area,
    search_area_summary,
)
from weedz.discovery.occurrences import NOT_QUERIED
from weedz.discovery.outcome_terms import EVIDENCE_FIELDS, Photos, plural, tally
from weedz.discovery.records import REGIONS, SPECIES, RunSpec
from weedz.discovery.sampling import SEASONS, season_of
from weedz.discovery.sharing import image_use, location, terms
from weedz.discovery.study import StudyDefinition, differences

Photo = dict[str, Any]
MEANING = (
    "What this run's incidental photos can and cannot support, before review. Counts are "
    "photos, the independent site visits among them, and photos that could not be "
    "grouped. A photo, area, period or year that was not collected, screened, compared "
    "or reviewed is unassessed: it is not evidence that no weed is there."
)
NOT_MEASURED = (
    "Not measured: no step estimates how much vegetation each photo shows. Featureless "
    "windows and pixel coverage say only what the screening could see"
)
NO_SNAPSHOT = "No reference snapshot to compare against"
NO_STUDY_PERIOD = "No study period is recorded, so photos are not checked against one"
BANDS: list[tuple[str, float]] = [
    (f"up to {SITE_CONTEXT_ACCURACY_M:g} m", SITE_CONTEXT_ACCURACY_M),
    ("20 to 100 m", 100.0),
    ("100 to 1,000 m", 1000.0),
    ("over 1,000 m", float("inf")),
]


def _incidental(export: dict[str, Any]) -> Photos:
    return [p for p in export["photos"] if p["cohort"] == "incidental"]


def _spec(export: dict[str, Any]) -> RunSpec | None:
    saved = export["run"].get("spec")
    return RunSpec.from_saved(saved) if saved else None


def _definition(export: dict[str, Any]) -> StudyDefinition | None:
    linked = export.get("study")
    return StudyDefinition.stored(linked["definition"]) if linked else None


def _scope_gaps(export: dict[str, Any], regions: dict[str, dict[str, int]]) -> list[str]:
    run = export["run"]
    gaps = [
        f"{name} returned {counts['photos']} of {counts['requested']} requested photos; "
        "the rest of its coverage is unassessed"
        for name, counts in regions.items()
        if counts["photos"] < counts["requested"]
    ]
    if run.get("status") != "completed":
        detail = f" ({run['detail']})" if run.get("detail") else ""
        gaps.append(
            f"The run is {run.get('status')}{detail}; this covers only the photos collected "
            "and screened so far"
        )
    if not export.get("references"):
        gaps.append(f"{NO_SNAPSHOT}: novelty is unassessed for every photo")
    return gaps


def scope(export: dict[str, Any], photos: Photos) -> dict[str, Any]:
    spec = _spec(export)
    found = Counter(p["region"] for p in photos)
    regions = {
        name: {"requested": spec.limit_per_region if spec else 0, "photos": found[name]}
        for name in REGIONS
    }
    others = Counter(p["cohort"] for p in export["photos"] if p["cohort"] != "incidental")
    return {
        "run_status": export["run"].get("status"),
        "incidental": tally(photos),
        "other_photos": dict(others),
        "regions": regions,
        "gaps": _scope_gaps(export, regions),
    }


def _span(observed: str | None) -> tuple[date, date] | None:
    """The first and last day the photo could have been taken: a day, month or year."""
    day = calendar_day(observed)
    if day or not observed:
        return (day, day) if day else None
    try:
        year, month = int(observed[:4]), int(observed[5:7] or 0)
        if not month:
            return date(year, 1, 1), date(year, 12, 31)
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    except ValueError:
        return None


def _in_period(photo: Photo, start: date | None, end: date | None) -> bool | None:
    """Inside the period, outside it, or unknown: undated, or a month or year across an end."""
    span = _span(photo.get("observed_on"))
    if span is None:
        return None
    first, last = span
    if (start and last < start) or (end and first > end):
        return False
    return None if (start and first < start) or (end and last > end) else True


def _placed(photos: Photos, study: StudyDefinition, inside: bool | None) -> Photos:
    """Photos inside the study period (True), outside it (False), or not placeable (None)."""
    start, end = study.period_start, study.period_end
    return [p for p in photos if _in_period(p, start, end) is inside]


def _month_range(first: date, last: date) -> set[tuple[int, int]]:
    """Every (year, month) from the first day's month to the last day's, inclusive."""
    start, stop = first.year * 12 + first.month - 1, last.year * 12 + last.month
    return {(index // 12, index % 12 + 1) for index in range(start, stop)}


def _covered(photos: Photos, start: date | None, end: date) -> set[tuple[int, int]]:
    """Every in-window (year, month) a photo's date could fall in. A month- or year-only
    date covers each month it spans, clipped to the window, so none looks empty."""
    months: set[tuple[int, int]] = set()
    for first, last in filter(None, (_span(p.get("observed_on")) for p in photos)):
        if (start is None or last >= start) and first <= end:
            months |= _month_range(max(first, start) if start else first, min(last, end))
    return months


Gaps = tuple[list[int] | None, list[str] | None]


def _gaps(photos: Photos, start: date | None, end: date) -> Gaps:
    """Years and seasons of the window no photo could fall in. Unknown (None) when an
    undated photo could fall anywhere, when the window was not sampled at all, and, for
    years, when it has an open start."""
    if (start and start > end) or any(_span(p.get("observed_on")) is None for p in photos):
        return None, None
    covered = _covered(photos, start, end)
    reached = {season_of(m) for _, m in _month_range(start, end)} if start else set(SEASONS)
    found = {season_of(m) for _, m in covered}
    seasons = [name for name in SEASONS if name in reached and name not in found]
    if start is None:
        return None, seasons
    years = {year for year, _ in covered}
    return [year for year in range(start.year, end.year + 1) if year not in years], seasons


Window = tuple[date | None, date]


def _window(export: dict[str, Any], study: StudyDefinition | None) -> Window:
    """The part of the study period the run queried (the query period for an open end).
    A study period wholly outside the query period ends before it starts."""
    spec = _spec(export) or RunSpec()
    after = spec.after if spec.sampling == "stratified" else None
    start = study.period_start if study and study.period_start else after
    end = study.period_end if study and study.period_end else spec.before
    return (max(start, after) if start and after else start), min(end, spec.before)


def _unsampled(study: StudyDefinition | None, window: Window) -> list[str]:
    """The ends of a partly queried study period that the run never queried."""
    start, end = window
    if study is None or (start and start > end):
        return []
    parts = []
    if start and study.period_start and study.period_start < start:
        parts.append(f"before {start.isoformat()}")
    if study.period_end and study.period_end > end:
        parts.append(f"after {end.isoformat()}")
    return parts


def _date_notes(
    dated: list[str], study: StudyDefinition | None, window: Window, gaps: int, undated: int
) -> list[str]:
    start, end = window
    notes = []
    if unsampled := _unsampled(study, window):
        notes.append(
            f"The study period {' and '.join(unsampled)} was not sampled (outside the run's "
            "query period); it is unassessed and its years are not listed as gaps"
        )
    if start is None and dated:
        notes.append(
            f"Recent sampling takes the newest photos first, so dates before {min(dated)} "
            "were not sampled; they are unassessed"
        )
    if start and start > end:
        notes.append(
            "The study period lies outside the run's query period, so none of it was "
            "sampled; it is unassessed"
        )
    if gaps:
        notes.append("Years and seasons with no photos are unassessed, not weed-free")
    if undated:
        notes.append(
            f"{plural(undated, 'undated photo')} could fall in any year or season, so gaps "
            "in coverage are unknown"
        )
    return notes


def _period(study: StudyDefinition | None) -> dict[str, str | None] | None:
    if study is None or not (study.period_start or study.period_end):
        return None
    start, end = study.period_start, study.period_end
    return {"start": start and start.isoformat(), "end": end and end.isoformat()}


def dates(export: dict[str, Any], photos: Photos, study: StudyDefinition | None) -> dict:
    spec = _spec(export)
    period = _period(study)
    start, end = _window(export, study)
    dated = [p["observed_on"][:10] for p in photos if p.get("observed_on")]
    corpus = export.get("corpus_coverage") or {}
    outside = unknown = None
    if study and period:
        outside, unknown = tally(_placed(photos, study, False)), tally(_placed(photos, study, None))
    years, seasons = _gaps(photos, start, end) if spec else ([], [])  # only if queried
    undated = sum(_span(p.get("observed_on")) is None for p in photos)
    return {
        "corpus": corpus,
        "earliest": min(dated, default=None),
        "latest": max(dated, default=None),
        "query_period": spec
        and {
            "start": spec.after.isoformat() if spec.sampling == "stratified" else None,
            "end": spec.before.isoformat(),
        },
        "study_period": period,
        "outside_study_period": outside,
        "study_period_unknown": unknown,
        "undated": tally([p for p in photos if not p.get("observed_on")]),
        "imprecise": tally(
            [p for p in photos if p.get("observed_on") and not calendar_day(p["observed_on"])]
        ),
        "years_without_photos": years,
        "seasons_without_photos": seasons,
        "notes": _date_notes(
            dated, study, (start, end), len(years or []) + len(seasons or []), undated
        ),
    }


def _accuracy(photos: Photos) -> dict[str, Any]:
    """Reported accuracy of public points; an obscured point's accuracy is of its offset."""
    public = [p for p in photos if p.get("coordinate_status") == "public"]
    values = sorted(
        p["positional_accuracy_m"] for p in public if p.get("positional_accuracy_m") is not None
    )
    bands = Counter(next(name for name, top in BANDS if value <= top) for value in values)
    return {
        "reported": len(values),
        "not_reported": len(public) - len(values),
        "min": values[0] if values else None,
        "median": statistics.median(values) if values else None,
        "max": values[-1] if values else None,
        "bands": {name: bands[name] for name, _ in BANDS},
    }


def locations(photos: Photos) -> dict[str, Any]:
    status = {p["id"]: search_area(p).status for p in photos}
    return {
        "search_areas": search_area_summary(photos),
        "not_searchable": {
            name: {"reason": reason} | tally([p for p in photos if status[p["id"]] == name])
            for name, reason in NOT_SEARCHABLE.items()
        },
        "accuracy_m": _accuracy(photos),
    }


def permitted_uses(photos: Photos) -> dict[str, Any]:
    images = Counter(image_use(p, "share").action for p in photos)
    shared = [location(p, "share") for p in photos]
    return {
        "photo_licences": dict(Counter(p["photo_license"] for p in photos)),
        "observation_licences": dict(Counter(p["observation_license"] for p in photos)),
        "non_commercial_only": sum(terms(p)["non_commercial"] for p in photos),
        "images": {"include": images["include"], "link": images["link"]},
        "image_link_reasons": dict(
            Counter(use.reason for p in photos if (use := image_use(p, "share")).action == "link")
        ),
        "locations": {
            "shared": sum(item.latitude is not None for item in shared),
            "withheld": dict(Counter(item.withheld for item in shared if item.withheld)),
            "none_supplied": sum(item.latitude is None and not item.withheld for item in shared),
        },
    }


MORE_FIELDS: dict[str, Callable[[Photo], bool]] = {
    "upload_date": lambda p: bool(p.get("uploaded_at")),
    "original_subject": lambda p: bool(p.get("original_taxon") or p.get("original_common_name")),
}


def missing(photos: Photos) -> dict[str, int]:
    """How many photos lack each piece of evidence; zero is stated, not left out."""
    fields = EVIDENCE_FIELDS | MORE_FIELDS
    return {name: sum(not check(p) for p in photos) for name, check in fields.items()}


def _subject(photo: Photo) -> str:
    common, taxon = photo.get("original_common_name"), photo.get("original_taxon")
    if common and taxon:
        return f"{common} ({taxon})"
    return common or taxon or "Not recorded"


def _recorded(photos: Photos, key: str) -> Counter[Any]:
    return Counter(p["scores"].get(key) for p in photos)


def screening(photos: Photos) -> dict[str, Any]:
    screened = [p for p in photos if p.get("scores")]
    coverage = _recorded(screened, "coverage_complete")
    featureless = [p["scores"].get("featureless_windows") for p in screened]
    waiting = {p["id"] for p in photos if p.get("review_status", "unreviewed") == "unreviewed"}
    return {
        "screened": tally(screened),
        "not_screened": tally([p for p in photos if not p.get("scores")]),
        "pixel_coverage": {
            "complete": coverage[True],
            "thinned": coverage[False],
            "not_recorded": coverage[None],
        },
        "featureless_windows": {
            "photos_with": sum(bool(windows) for windows in featureless),
            "not_recorded": featureless.count(None),
        },
        "visible_vegetation": NOT_MEASURED,
        "original_subjects": dict(Counter(map(_subject, photos)).most_common()),
        "reviewed": tally([p for p in photos if p["id"] not in waiting]),
        "unassessed": tally([p for p in photos if p["id"] in waiting]),
    }


def _not_compared(photo: Photo) -> str | None:
    """Why the photo was not compared with any watchlist species' records, or None."""
    found = photo.get("reference_comparison")
    if not found:
        return NO_SNAPSHOT
    if any(item["comparable"] for item in found.values()):
        return None
    # The photo's own reason applies to every species the snapshot queried.
    reasons = [item["reason"] for item in found.values()]
    return next((reason for reason in reasons if reason != NOT_QUERIED), reasons[0])


def reference_comparison(export: dict[str, Any], photos: Photos) -> dict[str, Any]:
    references = export.get("references")
    reasons = {p["id"]: _not_compared(p) for p in photos}
    snapshot = None
    if references:
        title = (references.get("dataset") or {}).get("title")
        snapshot = {"retrieved_at": references.get("retrieved_at"), "title": title}
    queried = (references or {}).get("taxon_keys") or {}
    return {
        "snapshot": snapshot,
        "not_queried_species": [name for name in SPECIES if name not in queried],
        "compared": tally([p for p in photos if reasons[p["id"]] is None]),
        "not_compared": {
            reason: tally([p for p in photos if reasons[p["id"]] == reason])
            for reason in dict.fromkeys(r for r in reasons.values() if r)
        },
    }


# Each conclusion a photo may be asked to support, and why a photo cannot support it.
LIMITS: list[tuple[str, str, str, Callable[[Photo], bool]]] = [
    (
        "field_search",
        "A field search lead",
        "No search area: the location is obscured, missing or of unknown accuracy",
        lambda p: search_area(p).status != "searchable",
    ),
    (
        "site_context",
        "Aerial site context",
        f"No public location accurate to {SITE_CONTEXT_ACCURACY_M:g} m or better",
        lambda p: not search_area(p).site_context,
    ),
    (
        "history",
        "When a plant was there",
        "The photo date is unknown",
        lambda p: not p.get("observed_on"),
    ),
    (
        "novelty",
        "Novelty against the reference records",
        "Not compared with the reference records",
        lambda p: _not_compared(p) is not None,
    ),
    (
        "independent_count",
        "Counting as an independent site visit",
        "Could not be grouped into a site visit (unknown, obscured or imprecise details)",
        lambda p: not p.get("encounter_linkable"),
    ),
    (
        "shared_image",
        "Sharing the image",
        "The photo licence is not admitted for sharing, so only a link can be given",
        lambda p: image_use(p, "share").action == "link",
    ),
    (
        "shared_location",
        "Sharing the location",
        "The location is withheld or was not supplied",
        lambda p: location(p, "share").latitude is None,
    ),
    (
        "screening",
        "Any screening suggestion",
        "Not screened yet",
        lambda p: not p.get("scores"),
    ),
]


def _study_period_limit(photos: Photos, study: StudyDefinition | None) -> dict[str, Any]:
    item = {"key": "study_period", "conclusion": "A conclusion about the study period"}
    if study is None or not (study.period_start or study.period_end):
        return item | {"because": NO_STUDY_PERIOD, "photos": None}
    because = "Photographed outside the study period, or not dated precisely enough to place in it"
    placed = _placed(photos, study, False) + _placed(photos, study, None)
    return item | {"because": because, "photos": tally(placed)}


def cannot_support(photos: Photos, study: StudyDefinition | None) -> list[dict[str, Any]]:
    """Each conclusion with the photos that cannot support it; None where not assessed."""
    items = [
        {"key": key, "conclusion": conclusion, "because": because}
        | {"photos": tally([p for p in photos if fails(p)])}
        for key, conclusion, because, fails in LIMITS
    ]
    return [*items[:3], _study_period_limit(photos, study), *items[3:]]


def _study(export: dict[str, Any], study: StudyDefinition | None) -> dict[str, Any] | None:
    linked = export.get("study")
    if not linked or study is None:
        return None
    return {
        "id": linked["id"],
        "version": linked["version"],
        "regions": [area.name for area in study.regions],
        "differences": differences(study, _spec(export)),
    }


def suitability(export: dict[str, Any]) -> dict[str, Any]:
    photos = _incidental(export)
    study = _definition(export)
    return {
        "schema": 1,
        "run_id": export["run"]["id"],
        "meaning": MEANING,
        "study": _study(export, study),
        "scope": scope(export, photos),
        "dates": dates(export, photos, study),
        "locations": locations(photos),
        "permitted_uses": permitted_uses(photos),
        "missing": missing(photos),
        "independence": export["encounters"]
        | {
            key: (export.get("corpus_coverage") or {}).get(key)
            for key in ("observers", "observer_days")
        },
        "screening": screening(photos),
        "reference_comparison": reference_comparison(export, photos),
        "cannot_support": cannot_support(photos, study),
    }
