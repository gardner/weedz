"""Noncommercial admission is explicit and never changes source rights or public defaults."""

from typing import Any

import pytest

from weedz.contract import Sample
from weedz.rights_profiles import require_rights, rights_profile_fields


def sample(media: str, metadata: str, **rights: Any) -> Sample:
    return Sample.model_validate(
        {
            "id": "test:1",
            "source": "test",
            "source_id": "1",
            "snapshot": "v1",
            "rights": {
                "media_license": media,
                "metadata_license": metadata,
                "attribution": "Original publisher",
                "license_source": "https://example.org",
                **rights,
            },
            "media": {"uri": "images/1.png", "sha256": "a" * 64},
            "tasks": ["inference"],
        }
    )


@pytest.mark.parametrize("licence", ["cc0", "cc0-1.0", "cc-by", "cc-by-3.0", "cc-by-4.0"])
def test_the_legacy_public_licences_stay_admitted(licence: str) -> None:
    require_rights(sample(licence, "cc-by-4.0"))


@pytest.mark.parametrize(
    "media,metadata",
    [
        ("cc-by-nc", "cc-by"),
        ("cc-by", "cc-by-nc"),
        ("cc-by-nc-4.0", "cc-by-nc-4.0"),
    ],
)
def test_either_nc_licence_requires_explicit_noncommercial_profile(
    media: str, metadata: str
) -> None:
    record = sample(media, metadata)
    with pytest.raises(ValueError, match="public"):
        require_rights(record)
    before = record.model_dump_json()
    require_rights(record, "noncommercial-cc0-by-nc")
    assert record.model_dump_json() == before


@pytest.mark.parametrize("licence", ["arr", "cc-by-sa-4.0", "cc-by-nd", "research-only", "unknown"])
def test_nc_opt_in_is_not_a_generic_permission_bypass(licence: str) -> None:
    with pytest.raises(ValueError, match="licence"):
        require_rights(sample("cc-by", licence), "noncommercial-cc0-by-nc")


def test_device_consent_is_not_a_source_licence_grant() -> None:
    record = sample("cc-by", "cc-by", consent={"version": "v1", "uses": ["training"]})
    with pytest.raises(ValueError, match="consent"):
        require_rights(record, "noncommercial-cc0-by-nc")


def test_an_unknown_profile_is_refused() -> None:
    with pytest.raises(ValueError, match="profile"):
        require_rights(sample("cc-by", "cc-by"), "anything-goes")  # type: ignore[arg-type]


def test_noncommercial_identity_is_explicit_while_public_identity_stays_legacy() -> None:
    assert rights_profile_fields("public-cc0-by") == {}
    assert rights_profile_fields("noncommercial-cc0-by-nc") == {
        "rights_profile": "noncommercial-cc0-by-nc"
    }
