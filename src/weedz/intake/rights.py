"""A device photo's rights as the contract carries them, from its person's consent (#60).

Review intake (#58) builds each device sample's `Rights` here, so the reference
collection and the sharing policy see the uses the person permitted, the licence and
credit they chose, and the wording they agreed to. The person chose one licence for
their contribution, so it covers the report's details as well as the photo.
"""

from weedz import consent
from weedz.contract import ContributorConsent, Rights
from weedz.intake.schema import Consent


def photo_rights(given: Consent) -> Rights | None:
    """The photo's rights, or None for a report sent without a photo."""
    if given.licence is None:
        return None
    return Rights(
        media_license=given.licence,
        metadata_license=given.licence,
        creator=given.credit,
        attribution=consent.attribution(given.licence, given.credit),
        license_source=consent.source(given.wording_version),
        consent=ContributorConsent(version=given.wording_version, uses=given.uses),
    )


def withdrawn(rights: Rights, at: str) -> Rights:
    """The rights once their person withdrew: what was agreed is kept, but permits nothing."""
    if rights.consent is None:
        raise ValueError("Only a contributor's own consent can be withdrawn")
    ended = rights.consent.model_copy(update={"withdrawn_at": at})
    return rights.model_copy(update={"consent": ended})
