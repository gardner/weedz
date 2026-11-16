"""A reference collection: what each reviewed example is, and which uses it may serve (P13).

Every annotation on a contract sample becomes one example. Its standing says whether it
is the source's original label, an accepted correction or confirmed suggestion, an
unresolved or unsuitable case, or not yet reviewed. Its eligibility for training,
evaluation and sharing is derived from the review outcome, whose label it is, and the
sharing policy (weedz.discovery.sharing), and, for a photo its contributor sent
directly, the uses they permitted (weedz.consent), always with the reason when it is not
eligible. Nothing is stored: the collection is re-derived from the append-only review
history, so it cannot disagree with it. No coordinates are carried; an example says
only whether its location could be shared, and why not.
"""

import re
from collections import Counter
from collections.abc import Iterable
from datetime import date
from typing import Any, Literal

from weedz.consent import Permission, refusal
from weedz.contract import Annotation, Sample
from weedz.discovery.sampling import season_of
from weedz.discovery.sharing import ADMITTED, NON_COMMERCIAL, location, not_admitted
from weedz.reference_gaps import NOT_RECORDED, coverage, gaps

Use = Literal["training", "evaluation", "sharing"]
USES: tuple[Use, ...] = ("training", "evaluation", "sharing")
# The permission each use needs from a photo's contributor (docs/report-consent.md).
NEEDS: dict[Use, Permission] = {
    "training": "training",
    "evaluation": "training",
    "sharing": "agencies",
}
Standing = Literal["original", "accepted", "unresolved", "unsuitable", "unreviewed"]
MEANING = (
    "Every reviewed or recorded label on this collection's photos, with what it is and "
    "which uses it may serve. Originals are the source's own labels; accepted examples "
    "are reviewer findings or screening suggestions that reviewers accepted. Unresolved "
    "and unsuitable examples are kept, but used for nothing. A missing example is a gap "
    "in the collection, never evidence that a weed is absent."
)
NO_TARGET = "The label is not present or absent, so no use has a target"
SET_ASIDE = {
    "unresolved": "Reviewers disagree or left it unresolved",
    # A rejected suggestion may well be a hard negative, but nothing records that the
    # species is absent rather than, say, unidentifiable, so no negative is invented.
    "unsuitable": "Rejected on review; a rejected claim is not turned into a negative example",
}
PREDICTION = "A screening suggestion nobody has accepted is a prediction, not a label"
SUGGESTED = (
    "Reviewers saw the suggestion they accepted, so it is not independent evidence for evaluation"
)
UNCONFIRMED = (
    "A reviewer's label is evaluation evidence only once accepted by someone other than its author"
)
UNREVIEWED = "Only original or accepted labels are shared as reference evidence"
NO_LOCATION = "No location was recorded"
VERSION = re.compile(r"-\d+(\.\d+)*$")


def licence_code(text: str) -> str:
    """A licence name as the sharing policy's code: "CC-BY-4.0" and "CC BY 4.0" are cc-by."""
    code = re.sub(r"[\s_]+", "-", text.strip().lower())
    return VERSION.sub("", code)


def standing(note: Annotation) -> Standing:
    if note.review == "rejected":
        return "unsuitable"
    if note.review == "uncertain":
        return "unresolved"
    if note.origin == "source":
        return "original"
    return "accepted" if note.review == "accepted" else "unreviewed"


def _set_aside(note: Annotation) -> str:
    """Why no use may rely on this label at all, or ""."""
    if note.label not in {"present", "absent"}:
        return NO_TARGET
    if reason := SET_ASIDE.get(standing(note), ""):
        return reason
    if note.origin == "model" and note.review != "accepted":
        return PREDICTION
    return ""


def _evaluation(note: Annotation) -> str:
    if note.origin == "model":
        return SUGGESTED
    others = set(note.reviewers) - {note.author}
    if note.origin == "reviewer" and not (note.review == "accepted" and others):
        return UNCONFIRMED
    return ""


def _sharing(sample: Sample, note: Annotation) -> str:
    if standing(note) not in {"original", "accepted"}:
        return UNREVIEWED
    for licence in (sample.rights.media_license, sample.rights.metadata_license):
        if licence_code(licence) not in ADMITTED:
            return not_admitted(licence)
    return ""


def _consented(sample: Sample) -> dict[Use, str]:
    """Per use, why the photo's contributor did not permit it, or "" (#60)."""
    given = sample.rights.consent
    if given is None:
        return dict.fromkeys(USES, "")
    return {use: refusal(given.uses, given.withdrawn_at, NEEDS[use]) for use in USES}


def _evidence(sample: Sample, note: Annotation) -> dict[Use, str]:
    if reason := _set_aside(note):
        return dict.fromkeys(USES, reason)
    return {"training": "", "evaluation": _evaluation(note), "sharing": _sharing(sample, note)}


def eligibility(sample: Sample, note: Annotation) -> dict[Use, str]:
    """Per use, "" when eligible, else why not: the contributor's consent first, then
    the label's evidence and the licences."""
    consented, evidence = _consented(sample), _evidence(sample, note)
    return {use: consented[use] or evidence[use] for use in USES}


def _location(sample: Sample) -> dict[str, Any]:
    """Whether the sample's point could be shared, by the sharing policy; never the point."""
    place = sample.geography
    if place is None:
        return {"shareable": False, "reason": NO_LOCATION}
    decided = location(
        {
            "latitude": place.latitude,
            "longitude": place.longitude,
            "coordinate_status": place.privacy,
            "positional_accuracy_m": place.uncertainty_m,
            "observation_license": licence_code(sample.rights.metadata_license),
            "consent": consent.model_dump() if (consent := sample.rights.consent) else None,
        },
        "share",
    )
    return {"shareable": not decided.withheld, "reason": decided.withheld}


def _season(captured_on: str | None) -> str:
    try:
        return season_of(date.fromisoformat((captured_on or "")[:10]).month)
    except ValueError:
        return "unknown"


def _rights(sample: Sample) -> dict[str, Any]:
    rights = sample.rights
    codes = {licence_code(rights.media_license), licence_code(rights.metadata_license)}
    return rights.model_dump(mode="json") | {"non_commercial": bool(codes & NON_COMMERCIAL)}


def _example(sample: Sample, note: Annotation) -> dict[str, Any]:
    verdicts = eligibility(sample, note)
    return {
        **({"category": note.category} if note.category is not None else {}),
        "sample_id": sample.id,
        "annotation_id": note.id,
        "source": sample.source,
        "taxon": note.taxon,
        "label": note.label,
        "supervision": note.supervision,
        "origin": note.origin,
        "standing": standing(note),
        "author": note.author,
        "reviewers": list(note.reviewers),
        "model": note.model,
        "recorded_at": note.recorded_at,
        "original_label": sample.original_label,
        "view": sample.view,
        "captured_on": sample.captured_on,
        "season": _season(sample.captured_on),
        "region": sample.context.get("region"),
        "rights": _rights(sample),
        "location": _location(sample),
        "uses": {
            use: {"eligible": not reason, "reason": reason} for use, reason in verdicts.items()
        },
    }


def examples(samples: Iterable[Sample]) -> list[dict[str, Any]]:
    return [_example(sample, note) for sample in samples for note in sample.annotations]


def _uses(found: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summary: dict[str, dict[str, Any]] = {}
    for use in USES:
        verdicts = [example["uses"][use] for example in found]
        refused = Counter(verdict["reason"] for verdict in verdicts if not verdict["eligible"])
        summary[use] = {
            "eligible": sum(verdict["eligible"] for verdict in verdicts),
            "not_eligible": dict(refused.most_common()),
        }
    return summary


def collection(name: str, samples: Iterable[Sample], expected: Iterable[str] = ()) -> dict:
    """The collection's examples, their standings and uses, and its coverage and gaps.
    `expected` names species to consider even when no example of them exists yet."""
    found = examples(samples)
    covered = coverage(found, USES, expected)
    missing, unknowns = gaps(found, covered)
    return {
        **(
            {"category_coverage": coverage(found, USES, target_field="category")}
            if any(example.get("category") for example in found)
            else {}
        ),
        "name": name,
        "meaning": MEANING,
        "examples": found,
        "standings": dict(Counter(example["standing"] for example in found).most_common()),
        "uses": _uses(found),
        "coverage": covered,
        "gaps": missing,
        "unknowns": unknowns,
        "not_recorded": NOT_RECORDED,
    }
