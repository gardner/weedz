"""The report a device sends once its person approves it: version 1 of the contract.

Strict by design: unknown fields, NaN and loosely typed values are refused. There is no
free text beyond an optional credit name, so a report carries no more personal data than
it needs. Location and capture time may be missing on the device (#54); when a location
is sent it carries its accuracy, since a point without one overstates where the photo
was taken. It is where the camera was, not the plant.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from weedz.consent import VERSIONS, Permission
from weedz.discovery.records import SPECIES
from weedz.discovery.sharing import ADMITTED

SCHEMA_VERSION = 1
# Phone clocks drift; a capture time further ahead than this is wrong, not early.
CLOCK_SKEW = timedelta(days=1)

Token = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")]
MeaningId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9./-]{0,119}$")]
Credit = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
# Standard base64 of a non-empty crop: ASCII only, so it never fails late as text.
Base64 = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9+/]+={0,2}$")]


class Part(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class Candidate(Part):
    """The suggested weed: a suggestion to be checked, not an identification."""

    taxon: str
    # A margin between two cosine similarities, so it lies in [-2, 2].
    score: float = Field(ge=-2, le=2)

    @field_validator("taxon")
    @classmethod
    def declared_target(cls, taxon: str) -> str:
        if taxon not in SPECIES:
            raise ValueError(f"Not a declared target taxon; expected one of {sorted(SPECIES)}")
        return taxon


class Screening(Part):
    """What produced the score, so it is compared only with like scores (#16)."""

    model_key: Token
    revision: Token
    ranking_revision: int = Field(ge=1, le=10_000)
    # None when the configuration has no declared score meaning.
    score_meaning: MeaningId | None = None


class Location(Part):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_m: float = Field(gt=0, le=100_000)


class Consent(Part):
    """What the person agreed to on the device, under which published wording (#60)."""

    wording_version: Token
    image: bool
    # What the photo may be used for. Review is why a photo is sent, so a photo always
    # permits it; a report without a photo permits no photo use at all.
    uses: frozenset[Permission] = frozenset()
    # The cropped image's licence: one the collection admits, and only with image consent.
    licence: str | None = None
    credit: Credit | None = None

    @field_validator("wording_version")
    @classmethod
    def published(cls, version: str) -> str:
        if version not in VERSIONS:
            raise ValueError(f"Not a published consent wording; expected one of {sorted(VERSIONS)}")
        return version

    @model_validator(mode="after")
    def uses_go_with_the_photo(self) -> "Consent":
        if self.image and "review" not in self.uses:
            raise ValueError("A photo is sent for review, so its uses include review")
        if not self.image and self.uses:
            raise ValueError("A report without a photo permits no photo use")
        return self

    @field_validator("licence")
    @classmethod
    def admitted(cls, licence: str | None) -> str | None:
        if licence is not None and licence not in ADMITTED:
            raise ValueError(f"Not an admitted licence; expected one of {sorted(ADMITTED)}")
        return licence

    @model_validator(mode="after")
    def licence_goes_with_image_consent(self) -> "Consent":
        if self.image != (self.licence is not None):
            raise ValueError("Image consent and an image licence go together")
        return self


class ReportContent(Part):
    """A report as stored: everything it says, without the crop, which is kept as a file."""

    schema_version: Literal[1]
    app_version: Token
    candidate: Candidate
    model: Screening
    captured_at: AwareDatetime | None = None
    location: Location | None = None
    consent: Consent

    @field_validator("captured_at")
    @classmethod
    def not_in_the_future(cls, captured: datetime | None) -> datetime | None:
        if captured is not None and captured > datetime.now(UTC) + CLOCK_SKEW:
            raise ValueError("The capture time is in the future")
        return captured


class Report(ReportContent):
    """A report as sent, with its optional crop."""

    # A base64 crop, sent only with image consent. Its size is bounded by the body limit.
    image: Base64 | None = None

    @model_validator(mode="after")
    def image_only_with_consent(self) -> "Report":
        if (self.image is not None) != self.consent.image:
            raise ValueError("An image is sent only with image consent, and consent needs one")
        return self
