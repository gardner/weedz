"""Explicit outbound dataset profiles; source rights are recorded, never rewritten."""

from typing import Literal

from weedz.contract import Sample

RightsProfile = Literal["public-cc0-by", "noncommercial-cc0-by-nc"]
PUBLIC_PROFILE: RightsProfile = "public-cc0-by"
NONCOMMERCIAL_PROFILE: RightsProfile = "noncommercial-cc0-by-nc"
PUBLIC = frozenset({"cc0", "cc0-1.0", "cc-by", "cc-by-3.0", "cc-by-4.0"})
NONCOMMERCIAL = PUBLIC | {"cc-by-nc", "cc-by-nc-3.0", "cc-by-nc-4.0"}
PROFILES: dict[RightsProfile, frozenset[str]] = {
    PUBLIC_PROFILE: PUBLIC,
    NONCOMMERCIAL_PROFILE: NONCOMMERCIAL,
}


def require_rights(sample: Sample, profile: RightsProfile = PUBLIC_PROFILE) -> None:
    """Check both licences under a named profile, without replacing contributor consent.

    These profiles cover sourced material. A directly contributed private image needs
    its separate consent workflow; a noncommercial flag is not permission to publish it.
    Custom publisher licences are not aliases for Creative Commons licences.
    """
    allowed = _licences(profile)
    rights = sample.rights
    if rights.consent is not None:
        raise ValueError("Source dataset profiles cannot replace contributor consent")
    if (
        rights.media_license.lower() not in allowed
        or rights.metadata_license.lower() not in allowed
    ):
        raise ValueError(f"Source media or metadata licence is outside the {profile} profile")


def rights_profile_fields(profile: RightsProfile = PUBLIC_PROFILE) -> dict[str, RightsProfile]:
    """The legacy public identity stays unchanged; noncommercial packages name their scope."""
    _licences(profile)
    return {} if profile == PUBLIC_PROFILE else {"rights_profile": profile}


def _licences(profile: RightsProfile) -> frozenset[str]:
    if profile not in PROFILES:
        raise ValueError(f"Unknown rights profile: {profile}")
    return PROFILES[profile]
