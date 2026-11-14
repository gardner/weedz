"""A release trains and tests models, so it holds only photos whose people permit that (#60)."""

import pytest
from test_release import RIGHTS, WHEN, close_sites, sites, spec

from weedz.contract import ContributorConsent, Sample
from weedz.release import build_release


def consented(record: Sample, uses: set[str], withdrawn_at: str | None = None) -> Sample:
    given = ContributorConsent.model_validate(
        {"version": "2026-11", "uses": uses, "withdrawn_at": withdrawn_at}
    )
    return record.model_copy(update={"rights": RIGHTS.model_copy(update={"consent": given})})


def test_a_release_takes_photos_whose_people_permit_training() -> None:
    samples = [consented(record, {"review", "training"}) for record in sites("a", "b", "c", "d")]
    _, kept = build_release(samples, spec(), recorded_at=WHEN)
    assert len(kept) == len(samples)


@pytest.mark.parametrize(
    ("uses", "withdrawn_at", "reason"),
    [
        ({"review", "agencies"}, None, "did not permit"),
        ({"review", "training"}, WHEN, "Withdrawn"),
    ],
)
def test_a_release_refuses_a_photo_its_person_did_not_permit_for_training(
    uses: set[str], withdrawn_at: str | None, reason: str
) -> None:
    samples = sites("a", "b", "c", "d")
    samples[0] = consented(samples[0], uses, withdrawn_at)
    with pytest.raises(ValueError, match=reason):
        build_release(samples, spec(), recorded_at=WHEN)


def test_a_photo_the_buffer_excludes_does_not_need_training_consent() -> None:
    samples = close_sites()
    index = next(i for i, record in enumerate(samples) if record.id == "test:22")
    samples[index] = consented(samples[index], {"review"})
    release, _ = build_release(samples, spec(buffer_m=2.0), recorded_at=WHEN)
    assert "test:22" in release.excluded
