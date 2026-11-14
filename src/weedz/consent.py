"""What a contributor permitted the project to do with their photo (issue #60).

A person approving a report on their device chooses, under a published version of the
consent text (docs/report-consent.md), which uses their photo may serve, its licence and
how they are credited. Every place a photo is used asks `refusal` for the permission that
use needs. Material from a source such as iNaturalist carries no consent record and stays
governed by its licence alone; a withdrawn consent permits nothing further.
"""

from collections.abc import Collection
from typing import Literal, get_args

Permission = Literal["review", "evidence", "agencies", "public", "training"]
PERMISSIONS: tuple[Permission, ...] = get_args(Permission)
# Published versions of the consent text, each a "## Version <id>" section of the document.
VERSIONS = frozenset({"2026-11"})
DOCUMENT = "docs/report-consent.md"
NOT_PERMITTED = {
    "review": "The contributor did not permit specialist review of this photo",
    "evidence": "The contributor did not permit keeping this photo as evidence after review",
    "agencies": "The contributor did not permit sharing this photo with weed agencies",
    "public": "The contributor did not permit sharing this photo publicly",
    "training": "The contributor did not permit using this photo to train or test models",
}
WITHDRAWN = "Withdrawn by the contributor, so the photo serves no further use"
LICENCE_NAMES = {"cc0": "CC0 1.0", "cc-by": "CC BY 4.0", "cc-by-nc": "CC BY-NC 4.0"}
ANONYMOUS = "a Weedz contributor"


def refusal(uses: Collection[str] | None, withdrawn_at: str | None, needed: Permission) -> str:
    """Why the contributor's consent does not allow this use, or "" when it does.
    `uses` is None for material no contributor consented to directly."""
    if uses is None:
        return ""
    if withdrawn_at:
        return WITHDRAWN
    return "" if needed in uses else NOT_PERMITTED[needed]


def attribution(licence: str, credit: str | None) -> str:
    """The credit a shared photo carries: the contributor's chosen name, never a guess."""
    who = f"{credit} via Weedz" if credit else ANONYMOUS
    return f"Photo: {who}, {LICENCE_NAMES[licence]}"


def source(version: str) -> str:
    """Where the wording a person agreed to is published."""
    return f"{DOCUMENT}#version-{version}"
