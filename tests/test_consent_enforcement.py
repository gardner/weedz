"""Every place a photo is used honours what its contributor permitted (#60)."""

import json
from pathlib import Path
from typing import Any

import pytest
from test_discovery import observation
from test_judgements import store_with_photo
from test_leads import select
from test_reference import note, reasons
from test_sharing import photo

from weedz.contract import Geography, Sample
from weedz.discovery import package, package_report
from weedz.discovery.activities import export
from weedz.discovery.audit import audit_sample
from weedz.discovery.records import RunSpec
from weedz.discovery.sharing import image_use, location, shareable_export, shareable_photo
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store
from weedz.reference import examples

WITHDRAWN_AT = "2026-11-14T00:00:00Z"


def consented(uses: list[str], withdrawn_at: str | None = None) -> dict[str, Any]:
    return {"version": "2026-11", "uses": uses, "withdrawn_at": withdrawn_at}


def device_sample(uses: list[str], withdrawn_at: str | None = None) -> Sample:
    return Sample.model_validate(
        {
            "id": "device:r1",
            "source": "device",
            "source_id": "r1",
            "snapshot": "intake",
            "rights": {
                "media_license": "cc-by",
                "metadata_license": "cc-by",
                "attribution": "Photo: Ana via Weedz, CC BY 4.0",
                "license_source": "docs/report-consent.md#version-2026-11",
                "consent": consented(uses, withdrawn_at),
            },
            "media": {"uri": "reports/images/x.jpg"},
            "tasks": ["inference"],
            "annotations": [
                note(origin="reviewer", author="kim", review="accepted", reviewers=["lee"])
            ],
        }
    )


def verdicts(record: Sample) -> dict[str, str]:
    (example,) = examples([record])
    return reasons(example)


def test_a_photo_without_training_consent_is_never_training_or_evaluation_eligible() -> None:
    found = verdicts(device_sample(["review", "agencies"]))
    assert "did not permit" in found["training"]
    assert "did not permit" in found["evaluation"]
    assert found["sharing"] == ""


def test_training_consent_makes_a_reviewed_photo_training_and_evaluation_eligible() -> None:
    found = verdicts(device_sample(["review", "training"]))
    assert found["training"] == found["evaluation"] == ""


def test_reference_sharing_needs_agency_sharing_consent() -> None:
    assert "did not permit" in verdicts(device_sample(["review", "training"]))["sharing"]


def test_withdrawal_removes_every_reference_eligibility() -> None:
    every = ["review", "evidence", "agencies", "public", "training"]
    found = verdicts(device_sample(every, WITHDRAWN_AT))
    assert all("Withdrawn" in reason for reason in found.values())


def test_review_shows_a_device_photo_only_with_review_consent() -> None:
    assert image_use(photo(consent=consented(["review"])), "review").action == "show"
    withdrawn = photo(consent=consented(["review"], WITHDRAWN_AT))
    assert image_use(withdrawn, "review").action == "link"


@pytest.mark.parametrize(
    ("uses", "action"),
    [(["review"], "link"), (["review", "training"], "link"), (["review", "agencies"], "include")],
)
def test_a_shared_output_includes_a_device_photo_only_with_agency_consent(
    uses: list[str], action: str
) -> None:
    decided = image_use(photo(consent=consented(uses)), "share")
    assert decided.action == action
    if action == "link":
        assert "did not permit" in decided.reason


def test_a_licence_the_collection_refuses_is_still_refused_with_consent() -> None:
    item = photo(photo_license="cc-by-sa", consent=consented(["review", "agencies"]))
    assert image_use(item, "share").action == "link"


def test_attribution_and_the_contributors_limits_travel_with_a_shared_photo() -> None:
    credit = "Photo: Ana Smith via Weedz, CC BY 4.0"
    item = photo(
        photo_license="cc-by", attribution=credit, consent=consented(["review", "agencies"])
    )
    shared = shareable_photo(item)["sharing"]
    assert shared["terms"]["attribution"] == credit
    assert shared["terms"]["contributor_permits"] == ["agencies", "review"]
    assert shared["image"]["action"] == "include"


def test_a_withdrawn_photo_is_shared_as_permitting_nothing() -> None:
    item = photo(consent=consented(["review", "agencies"], WITHDRAWN_AT))
    shared = shareable_photo(item)["sharing"]
    assert shared["terms"]["contributor_permits"] == []
    assert shared["image"]["action"] == "link"


def test_sourced_photos_carry_no_contributor_limits() -> None:
    assert "contributor_permits" not in shareable_photo(photo())["sharing"]["terms"]


def test_a_follow_up_package_tells_the_agency_what_the_contributor_permits() -> None:
    item = photo(photo_license="cc-by", consent=consented(["review", "agencies"]))
    entry = package.image(item, [])
    assert entry["included"] is True
    assert entry["contributor_permits"] == ["agencies", "review"]
    source = {key: item[key] for key in ("observer", "attribution")} | {
        "url": item["source_url"],
        "photo_license": "cc-by",
        "observation_license": "cc-by",
        "observation_terms": "x",
    }
    lines = package_report._source({"photo_id": item["id"], "source": source, "image": entry})
    assert any("permits only: agencies, review" in line for line in lines)


def test_a_sourced_photo_in_a_package_carries_no_contributor_limits() -> None:
    assert "contributor_permits" not in package.image(photo(), [])


def test_a_withdrawn_photo_never_gives_its_location() -> None:
    item = photo(consent=consented(["review", "agencies"], WITHDRAWN_AT))
    for use in ("review", "share"):
        decided = location(item, use)
        assert decided.latitude is None and "withdrew" in decided.withheld


def test_a_withdrawn_photo_is_left_out_of_shared_exports() -> None:
    kept = photo(id="kept", consent=consented(["review", "agencies"]))
    gone = photo(id="gone", consent=consented(["review", "agencies"], WITHDRAWN_AT))
    shared = shareable_export({"photos": [kept, gone, photo(id="sourced")]})
    assert [item["id"] for item in shared["photos"]] == ["kept", "sourced"]


def test_a_withdrawn_photo_is_left_out_of_follow_up_packages() -> None:
    gone = photo(id="gone", findings=[], consent=consented(["review", "agencies"], WITHDRAWN_AT))
    export = {
        "photos": [gone],
        "run": {"id": "r", "created_at": "t", "model": "m"},
        "references": None,
    }
    selection = {
        "id": 1,
        "action": "selected",
        "photo_id": "gone",
        "finding_id": None,
        "selector": "kim",
        "reason": "",
        "created_at": "t",
    }
    assert package.follow_up_package(export, [selection], "t")["leads"] == []


def test_nothing_derived_from_a_withdrawn_photo_is_exported(tmp_path: Path) -> None:
    store, photo_id = store_with_photo(tmp_path)
    select(store, photo_id)
    stored = store.photos
    ended = consented(["review", "agencies"], WITHDRAWN_AT)
    store.photos = lambda run_id: [item | {"consent": ended} for item in stored(run_id)]  # type: ignore[method-assign]
    shared = json.dumps(shareable_export(export(store, "run")))
    assert photo_id not in shared


def test_a_withdrawal_leaves_the_rest_of_the_audit_sample_as_the_review_app_draws_it(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path)
    store.create_run("run", RunSpec())
    records = [
        photo_from_observation(observation() | {"id": 100 + index}, "Nelson", "incidental")
        for index in range(8)
    ]
    store.save_photos("run", [record for record in records if record is not None])
    drawn = audit_sample("run", store.photos("run"))
    outside = next(item["id"] for item in store.photos("run") if item["id"] not in drawn)
    ended = consented(["review"], WITHDRAWN_AT)
    stored = store.photos
    for gone in (sorted(drawn)[0], outside):
        store.photos = lambda run_id, gone=gone: [  # type: ignore[method-assign]
            item | {"consent": ended} if item["id"] == gone else item for item in stored(run_id)
        ]
        assert export(store, "run")["audit"]["sampled"] == len(drawn - {gone})


def test_a_withdrawn_reference_example_says_its_location_cannot_be_shared() -> None:
    record = device_sample(["review", "agencies"], WITHDRAWN_AT).model_copy(
        update={"geography": Geography(latitude=-41.3, longitude=173.2, uncertainty_m=10)}
    )
    (example,) = examples([record])
    assert example["location"]["shareable"] is False
    assert "withdrew" in example["location"]["reason"]
