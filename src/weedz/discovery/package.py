"""A follow-up package: the leads the team selected, each with its evidence and limits.

Built from a run export and its lead selections (PRD P12, Journey 4). Only selected leads
are included, never the whole queue. Each lead keeps its source, attribution and licences,
its reviewers' opinions and disagreement, its search area or why there is none, its dates,
its comparison basis and the reason it was selected. Raw coordinates are never copied: a
location appears only as a search area centred on a public observation point. A photo is
packaged only when its licence permits redistribution; otherwise the lead links to it.
"""

from typing import Any

from weedz.discovery.judgements import JUDGEMENTS, disputes, judged_taxon
from weedz.discovery.leads import selected_leads
from weedz.discovery.outcome_novelty import RECORD_RELATIVE, level
from weedz.discovery.records import SPECIES

# Licences the collection accepts, all of which permit sharing the photo with attribution.
REDISTRIBUTABLE = {
    "cc0": "CC0: no rights reserved; attribution kept as a courtesy",
    "cc-by": "CC BY: share with the attribution shown",
    "cc-by-nc": "CC BY-NC: share with the attribution shown, for non-commercial use only",
}
LINK_ONLY = (
    "Not included: the photo licence ({licence}) does not clearly permit redistribution "
    "here, so follow the source link to view it"
)
WINDOW = "Screening window: where the model looked, a search region, not a plant boundary"
EXTENT = "Reviewer-drawn visible extent of this plant"
UNCOMPARED = (
    "No reference records were compared for this plant, so novelty against records is "
    "unassessed and no new locality is claimed"
)
READING = [
    "Only leads the team selected for follow-up are included, each with who selected it and why.",
    "Search areas are centred on the observation point (where the photographer was), never "
    "a plant point; obscured, missing or unknown-accuracy locations have none.",
    "A photo shows a plant was there when photographed, not that it is there now.",
    "Judgements are attributed reviewer opinions; 'disputed' means reviewers differ, and "
    "'unassessed' means nobody has judged. Only a noted verified_new_locality claims a "
    "new locality.",
    "Comparisons are distances and dates to one declared reference snapshot; a missing "
    "record is not evidence of absence.",
    "Photos in the same site-visit group are related evidence, not separate infestations.",
    "Photos are shared under their own licences with attribution. Do not publish them, or "
    "a new observation, on the observer's behalf.",
]


def image(photo: dict[str, Any], detail: list[dict[str, Any]]) -> dict[str, Any]:
    """The photo when its licence permits redistribution, else a pointer to the source."""
    terms = REDISTRIBUTABLE.get(photo["photo_license"])
    return {
        "included": terms is not None,
        "file": f"photos/{photo['id']}.jpg" if terms else None,
        "sha256": photo.get("sha256") or None,
        "terms": terms or LINK_ONLY.format(licence=photo["photo_license"] or "none"),
        "source_url": photo["source_url"],
        "detail": detail,
    }


def _candidate(photo: dict[str, Any], plant: dict[str, Any] | None) -> dict[str, Any]:
    if plant is None:
        species = photo["scores"].get("best_species")
        return {"kind": "suggestion", "species": species, "recorded_by": None, "note": ""} | {
            "common_name": SPECIES.get(species or "")
        }
    species = plant["species"] or plant["other_taxon"]
    return {
        "kind": plant["kind"],
        "species": species,
        "common_name": SPECIES.get(plant["species"] or ""),
        "recorded_by": plant["reviewer"],
        "note": plant["note"],
    }


def _detail(photo: dict[str, Any], plant: dict[str, Any] | None) -> list[dict[str, Any]]:
    box, label = (photo["scores"].get("box"), WINDOW) if plant is None else (plant["box"], EXTENT)
    return [{"box": list(box), "is": label}] if box else []


def _judgements(standing: dict[str, dict[str, dict]]) -> dict[str, Any]:
    keep = ("value", "note", "created_at")
    judged: dict[str, Any] = {
        dimension: {
            "level": level(standing.get(dimension, {})),
            "by_reviewer": {
                name: {key: opinion[key] for key in keep}
                for name, opinion in standing.get(dimension, {}).items()
            },
        }
        for dimension in JUDGEMENTS
    }
    return judged | {"disputed_dimensions": disputes(standing)}


def _comparison(
    photo: dict[str, Any], species: str | None, snapshot: dict | None, novelty: dict[str, dict]
) -> dict[str, Any]:
    found = (photo.get("reference_comparison") or {}).get(species or "")
    sha = snapshot and snapshot["snapshot_sha256"]
    return {
        "snapshot": snapshot,
        "records_near_photo": found,
        "note": UNCOMPARED if not (found and found.get("comparable")) else "",
        "judged_novelty": level(novelty),
        "judged_against_another_snapshot": any(
            opinion["value"] in RECORD_RELATIVE and opinion.get("reference_snapshot") != sha
            for opinion in novelty.values()
        ),
    }


def _referrals(photo: dict[str, Any], finding_id: int | None) -> list[dict[str, Any]]:
    """Referrals of this plant, and of the whole photo, which cover every plant on it."""
    return [
        referral
        for referral in photo.get("referrals", [])
        if referral["finding_id"] in {None, finding_id}
    ]


def _source(photo: dict[str, Any]) -> dict[str, Any]:
    keys = ("observer", "attribution", "photo_license", "observation_license")
    return {"url": photo["source_url"], **{key: photo[key] for key in keys}}


def _event(event: dict[str, Any]) -> dict[str, Any]:
    return {key: event[key] for key in ("action", "selector", "reason", "created_at")}


def lead(photo: dict[str, Any], selection: dict[str, Any], snapshot: dict | None) -> dict:
    finding_id = selection["finding_id"]
    plant = next((item for item in photo["findings"] if item["id"] == finding_id), None)
    standing = (plant or photo)["judgements"]
    candidate = _candidate(photo, plant)
    keep = ("selector", "reason", "created_at")
    return {
        "photo_id": photo["id"],
        "finding_id": finding_id,
        "region": photo["region"],
        "selection": {key: selection[key] for key in keep}
        | {
            "history": [
                {key: event[key] for key in ("action", *keep)} for event in selection["history"]
            ]
        },
        "candidate": candidate,
        "original_subject": {
            "taxon": photo["original_taxon"],
            "common_name": photo["original_common_name"],
        },
        "source": _source(photo),
        "image": image(photo, _detail(photo, plant)),
        "review": {
            "about": "the suggested species",
            "latest_decision": photo["review_status"],
            "reviewer_decisions": photo["reviewer_decisions"],
            "reviewers_disagree": photo["disputed"],
        },
        "judgements": _judgements(standing),
        "referrals": _referrals(photo, finding_id),
        "limits": photo["limits"],
        # Compared by watchlist key only: free text is never matched to the records.
        "comparison": _comparison(
            photo, judged_taxon(photo, finding_id), snapshot, standing.get("novelty", {})
        ),
        "site_visit": {
            "group": photo["encounter_group"],
            "photos_in_group": photo["encounter_size"],
            "could_be_grouped": photo["encounter_linkable"],
        },
    }


def follow_up_package(
    export: dict[str, Any], events: list[dict[str, Any]], generated_at: str
) -> dict[str, Any]:
    """The run's selected leads, oldest selection first, with how to read them."""
    photos = {photo["id"]: photo for photo in export["photos"]}
    run = export["run"]
    return {
        "schema": 1,
        "kind": "weedz follow-up package",
        "run": {"id": run["id"], "created_at": run["created_at"], "model": run["model"]},
        "generated_at": generated_at,
        "reference_snapshot": export["references"],
        "how_to_read": READING,
        "leads": [
            lead(photos[selection["photo_id"]], selection, export["references"])
            for selection in selected_leads(events)
        ],
    }
