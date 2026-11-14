"""What may leave the project, for each photo and use (PRD P15, P17).

One policy for every outbound path. `review` is the local review app on the reviewer's
own machine; `share` is anything that leaves it, such as the run export or a follow-up
package. For each photo the policy decides whether its image may be shown, included or
only linked, which attribution and licence terms must travel with it, and which
location may leave. An obscured point never leaves; a shared public point always
carries its accuracy. Nothing here, or anywhere in the project, publishes to a source.
"""

from typing import Any, Literal, NamedTuple

from weedz.consent import Permission, refusal

Use = Literal["review", "share"]
# The permission each use needs from a photo's contributor (docs/report-consent.md): every
# outbound path goes to agencies and partners; none publishes.
NEEDS: dict[Use, Permission] = {"review": "review", "share": "agencies"}

# Photo licences the collection admits (docs/datasets.md, "Project purpose and source
# reuse"), each with what sharing a photo under it requires.
ADMITTED = {
    "cc0": "CC0: no rights reserved; attribution kept as a courtesy",
    "cc-by": "CC BY: share with the attribution shown",
    "cc-by-nc": "CC BY-NC: share with the attribution shown, for non-commercial use only",
}
# What observation data (taxon, date, observer, location) requires under its licence.
OBSERVATION_TERMS = {
    "cc0": "Observation data CC0: no rights reserved; credit kept as a courtesy",
    "cc-by": "Observation data CC BY: credit the observer and link the source",
    "cc-by-nc": "Observation data CC BY-NC: credit the observer and link the source, for "
    "non-commercial use only",
}
NON_COMMERCIAL = {"cc-by-nc"}
NO_DERIVATIVES = (
    "Not admitted: a no-derivatives (ND) licence ({licence}) allows only verbatim copies, "
    "and verbatim-only handling is not implemented, so follow the source link"
)
SHARE_ALIKE = (
    "Not admitted: a share-alike (SA) licence ({licence}) binds derived material to the "
    "same terms, which are not yet carried, so follow the source link"
)
RESERVED = (
    "Not admitted: all rights reserved, and the observer's permission is not established, "
    "so follow the source link"
)
UNKNOWN = "Not admitted: the licence {licence} is not one the collection accepts"
WITHHELD = {
    "obscured": "Withheld: the source obscured this location, so its displaced point is "
    "never passed on",
    "not_public": "Withheld: the source did not mark this location public",
    "accuracy_unknown": "Withheld: the location's accuracy was not supplied, and a point "
    "without its uncertainty would overstate where the photo was taken",
    "observation_licence": "Withheld: the observation licence is not admitted, so its "
    "location is not passed on",
}
SHARING = [
    "Photos and observations keep their own licences: credit the attribution shown, link "
    "the source, and use CC BY-NC material for non-commercial purposes only.",
    "Only CC0, CC BY and CC BY-NC photos are included; any other licence is linked, with "
    "the reason.",
    "An obscured location is never given; a public location is given only with its "
    "accuracy, and it marks where the photographer was, not a plant.",
    "Nothing is published to iNaturalist or GBIF, and no observation is created on "
    "anyone's behalf.",
]


class ImageUse(NamedTuple):
    action: Literal["show", "include", "link"]
    reason: str


class Location(NamedTuple):
    status: str
    latitude: float | None
    longitude: float | None
    accuracy_m: float | None
    withheld: str


def not_admitted(licence: str | None) -> str:
    """Why a licence the collection does not accept is linked rather than used."""
    code = (licence or "").lower()
    if not code or code in {"arr", "all-rights-reserved"}:
        return RESERVED
    if "nd" in code.split("-"):
        return NO_DERIVATIVES.format(licence=licence)
    if "sa" in code.split("-"):
        return SHARE_ALIKE.format(licence=licence)
    return UNKNOWN.format(licence=licence)


def refuse_unadmitted(photo_license: str, observation_license: str) -> None:
    """Refuse a photo or observation the collection does not admit, whatever its source."""
    for kind, licence in (("photo", photo_license), ("observation", observation_license)):
        if licence not in ADMITTED:
            raise ValueError(f"Refused {kind} licence {licence!r}. {not_admitted(licence)}")


def contributor_refusal(photo: dict[str, Any], use: Use) -> str:
    """Why the photo's contributor did not permit this use, or "" (#60). A sourced photo
    has no consent record and is governed by its licence alone."""
    given = photo.get("consent")
    if not given:
        return ""
    return refusal(given["uses"], given.get("withdrawn_at"), NEEDS[use])


def image_use(photo: dict[str, Any], use: Use) -> ImageUse:
    """Whether the photo may be shown (review) or included (share), or only linked."""
    licence = photo.get("photo_license")
    terms = ADMITTED.get(licence or "")
    if terms is None:
        return ImageUse("link", not_admitted(licence))
    if refused := contributor_refusal(photo, use):
        return ImageUse("link", refused)
    return ImageUse("show" if use == "review" else "include", terms)


def terms(photo: dict[str, Any]) -> dict[str, Any]:
    """The attribution and licence conditions that travel with the photo wherever it goes."""
    photo_licence, observation_licence = photo["photo_license"], photo["observation_license"]
    return {
        "attribution": photo["attribution"],
        "observer": photo["observer"],
        "source_url": photo["source_url"],
        "photo_licence": photo_licence,
        "photo_terms": ADMITTED.get(photo_licence) or not_admitted(photo_licence),
        "observation_licence": observation_licence,
        "observation_terms": OBSERVATION_TERMS.get(observation_licence)
        or not_admitted(observation_licence),
        "non_commercial": bool({photo_licence, observation_licence} & NON_COMMERCIAL),
    } | _contributor_limits(photo)


def _contributor_limits(photo: dict[str, Any]) -> dict[str, Any]:
    """The uses a contributor permitted, so a recipient knows, e.g., not to publish."""
    given = photo.get("consent")
    return {"contributor_permits": sorted(given["uses"])} if given else {}


def _withheld(photo: dict[str, Any], use: Use) -> str:
    if photo.get("coordinate_status") == "obscured":
        return WITHHELD["obscured"]
    if photo.get("coordinate_status") != "public":
        return WITHHELD["not_public"]
    if use == "review":
        return ""
    if photo.get("observation_license") not in OBSERVATION_TERMS:
        return WITHHELD["observation_licence"]
    if photo.get("positional_accuracy_m") is None:
        return WITHHELD["accuracy_unknown"]
    return ""


def location(photo: dict[str, Any], use: Use) -> Location:
    """The point that may leave for this use, with its accuracy, or why it is withheld."""
    status = photo.get("coordinate_status") or "missing"
    accuracy = photo.get("positional_accuracy_m")
    if photo.get("latitude") is None or photo.get("longitude") is None:
        return Location(status, None, None, accuracy, "")
    reason = _withheld(photo, use)
    if reason:
        return Location(status, None, None, accuracy, reason)
    return Location(status, photo["latitude"], photo["longitude"], accuracy, "")


def with_location(photo: dict[str, Any], use: Use) -> dict[str, Any]:
    """The photo with only the coordinates this use may carry; a withheld point takes
    any search area centred on it along."""
    allowed = location(photo, use)
    kept = photo | {"latitude": allowed.latitude, "longitude": allowed.longitude}
    area = (photo.get("limits") or {}).get("search_area") or {}
    if allowed.withheld and area.get("centre") is not None:
        hidden = area | {
            "status": "withheld",
            "reason": allowed.withheld,
            "centre": None,
            "radius_m": None,
            "site_context": False,
        }
        kept["limits"] = photo["limits"] | {"search_area": hidden}
    return kept


def shareable_photo(photo: dict[str, Any]) -> dict[str, Any]:
    allowed = location(photo, "share")
    return with_location(photo, "share") | {
        "sharing": {
            "terms": terms(photo),
            "image": image_use(photo, "share")._asdict(),
            "location": allowed._asdict(),
        }
    }


def shareable_export(export: dict[str, Any]) -> dict[str, Any]:
    """The run export as it may leave the reviewer's machine: points withheld by the
    location rule, and each photo's terms and image decision stated."""
    return export | {
        "photos": [shareable_photo(photo) for photo in export["photos"]],
        "sharing": SHARING,
    }
