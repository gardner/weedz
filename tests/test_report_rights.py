"""What a contributor agreed to for their photo, under which wording, and its credit (#60)."""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from weedz.consent import PERMISSIONS, VERSIONS, Permission, attribution, refusal
from weedz.contract import Rights
from weedz.intake.rights import photo_rights, withdrawn
from weedz.intake.schema import Consent

CONSENT_TEXT = Path(__file__).parents[1] / "docs" / "report-consent.md"


def consent(**fields: Any) -> Consent:
    record = {
        "wording_version": "2026-11",
        "image": True,
        "uses": ["review"],
        "licence": "cc-by-nc",
    } | fields
    # As a device sends it: JSON, which the strict schema reads.
    return Consent.model_validate_json(json.dumps(record))


def test_every_published_wording_version_has_its_text_in_the_consent_document() -> None:
    sections = set(re.findall(r"^## Version (\S+)$", CONSENT_TEXT.read_text(), re.MULTILINE))
    assert sections >= VERSIONS
    assert sections <= VERSIONS


def test_the_consent_document_names_every_use_a_person_can_permit() -> None:
    text = CONSENT_TEXT.read_text()
    for use in PERMISSIONS:
        assert f"`{use}`" in text


def test_the_wording_version_is_required() -> None:
    with pytest.raises(ValidationError):
        Consent.model_validate_json('{"image": false}')


def test_an_unpublished_wording_version_is_refused() -> None:
    with pytest.raises(ValidationError, match="published"):
        consent(wording_version="2099-01")


def test_the_wording_version_is_stored_with_the_rights() -> None:
    rights = photo_rights(consent(uses=["review", "training"]))
    assert rights is not None
    assert rights.consent is not None
    assert rights.consent.version == "2026-11"
    assert rights.consent.uses == frozenset({"review", "training"})


def test_a_photo_needs_review_permission_since_review_is_why_it_is_sent() -> None:
    with pytest.raises(ValidationError, match="review"):
        consent(uses=["training"])


def test_a_report_without_a_photo_permits_no_photo_use() -> None:
    with pytest.raises(ValidationError):
        consent(image=False, licence=None, uses=["review"])
    assert photo_rights(consent(image=False, licence=None, uses=[])) is None


def test_an_unknown_use_is_refused() -> None:
    with pytest.raises(ValidationError):
        consent(uses=["review", "advertising"])


@pytest.mark.parametrize("licence", ["cc-by-sa", "cc-by-nd", "cc-by-nc-sa", "arr", "gpl-3.0", ""])
def test_an_unknown_or_unsupported_licence_is_refused(licence: str) -> None:
    with pytest.raises(ValidationError, match="admitted licence"):
        consent(licence=licence)


@pytest.mark.parametrize(
    ("licence", "credit", "expected"),
    [
        ("cc-by", "Ana Smith", "Photo: Ana Smith via Weedz, CC BY 4.0"),
        ("cc-by-nc", None, "Photo: a Weedz contributor, CC BY-NC 4.0"),
        ("cc0", "Ana Smith", "Photo: Ana Smith via Weedz, CC0 1.0"),
    ],
)
def test_attribution_follows_the_chosen_licence_and_credit(
    licence: str, credit: str | None, expected: str
) -> None:
    assert attribution(licence, credit) == expected


def test_the_rights_carry_the_licence_and_the_credit_for_photo_and_details() -> None:
    rights = photo_rights(consent(licence="cc-by", credit="Ana Smith"))
    assert rights is not None
    assert (rights.media_license, rights.metadata_license) == ("cc-by", "cc-by")
    assert rights.creator == "Ana Smith"
    assert rights.attribution == "Photo: Ana Smith via Weedz, CC BY 4.0"
    assert rights.license_source == "docs/report-consent.md#version-2026-11"


def test_no_credit_name_is_never_guessed() -> None:
    rights = photo_rights(consent())
    assert rights is not None
    assert rights.creator is None
    assert "a Weedz contributor" in rights.attribution


@pytest.mark.parametrize("use", PERMISSIONS)
def test_each_use_is_refused_unless_permitted(use: Permission) -> None:
    assert refusal(frozenset({use}), None, use) == ""
    others = frozenset(PERMISSIONS) - {use}
    assert "did not permit" in refusal(others, None, use)


def test_material_without_contributor_consent_is_governed_by_its_licence_alone() -> None:
    assert refusal(None, None, "training") == ""


def test_withdrawal_refuses_every_use() -> None:
    granted = frozenset(PERMISSIONS)
    for use in PERMISSIONS:
        assert "Withdrawn" in refusal(granted, "2026-11-14T00:00:00Z", use)


def test_withdrawn_rights_keep_what_was_agreed_and_when_it_ended() -> None:
    rights = photo_rights(consent(uses=["review", "training"]))
    assert rights is not None
    ended = withdrawn(rights, "2026-11-14T00:00:00Z")
    assert ended.consent is not None
    assert ended.consent.withdrawn_at == "2026-11-14T00:00:00Z"
    assert ended.consent.uses == frozenset({"review", "training"})


def test_rights_without_consent_serialise_as_before() -> None:
    rights = Rights(
        media_license="cc-by", metadata_license="cc0", attribution="x", license_source="y"
    )
    assert "consent" not in rights.model_dump_json()


def test_consented_rights_round_trip() -> None:
    rights = photo_rights(consent(uses=["training", "review"]))
    assert rights is not None
    assert Rights.model_validate_json(rights.model_dump_json()) == rights
    assert '"uses":["review","training"]' in rights.model_dump_json()
