"""The regional pilot keeps source identity, review decisions and retries honest."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from weedz.discovery.records import Photo, RunSpec
from weedz.discovery.source import photo_from_observation
from weedz.discovery.store import Store


def observation() -> dict:
    return {
        "id": 100,
        "uri": "https://www.inaturalist.org/observations/100",
        "license_code": "cc-by-nc",
        "observed_on": "2024-06-01",
        "created_at": "2024-06-02T00:00:00Z",
        "location": "-41.2,173.3",
        "positional_accuracy": 100,
        "geoprivacy": "obscured",
        "obscured": True,
        "taxon": {"name": "Turdus merula", "preferred_common_name": "Blackbird"},
        "user": {"login": "observer"},
        "photos": [
            {
                "id": 101,
                "license_code": "cc-by-nc",
                "attribution": "Example observer (CC BY-NC 4.0)",
                "url": "https://inaturalist-open-data.s3.amazonaws.com/photos/101/square.jpg",
            }
        ],
    }


def test_source_keeps_original_subject_separate_and_location_uncertainty() -> None:
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo is not None
    assert photo.original_taxon == "Turdus merula"
    assert photo.cohort == "incidental"
    assert photo.coordinate_status == "obscured"
    assert photo.observed_on == "2024-06-01"
    assert photo.photo_license == "cc-by-nc"
    assert photo.image_url.endswith("/large.jpg")
    assert photo.reference_species is None


def test_ineligible_photo_is_skipped_even_if_observation_is_licensed() -> None:
    raw = observation()
    raw["photos"][0]["license_code"] = None
    assert photo_from_observation(raw, "Tasman", "incidental") is None
    raw = observation()
    raw["license_code"] = None
    assert photo_from_observation(raw, "Tasman", "incidental") is None


def test_control_is_explicit_and_unknown_location_stays_unknown() -> None:
    raw = observation()
    raw["location"] = None
    photo = photo_from_observation(raw, "Tasman", "reference", "Clematis vitalba")
    assert photo is not None
    assert photo.reference_species == "Clematis vitalba"
    assert photo.latitude is None and photo.longitude is None
    assert photo.coordinate_status == "missing"


def test_bounded_run_and_valid_date() -> None:
    with pytest.raises(ValidationError):
        RunSpec(limit_per_region=10000)
    with pytest.raises(ValidationError):
        RunSpec.model_validate({"before": "not-a-date"})


def test_activity_retry_does_not_duplicate_or_erase_reviews(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.create_run("run-1", RunSpec())
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert isinstance(photo, Photo)
    store.save_photos("run-1", [photo])
    store.review("run-1", photo.id, "uncertain", "Need a flowering view")
    store.save_photos("run-1", [photo])
    photos = store.photos("run-1")
    assert len(photos) == 1
    assert photos[0]["review_status"] == "uncertain"
    assert len(store.reviews("run-1", photo.id)) == 1
    store.review("run-1", photo.id, "rejected", "Native lookalike")
    assert len(store.reviews("run-1", photo.id)) == 2


def test_unknown_review_cannot_create_a_phantom_photo(tmp_path: Path) -> None:
    store = Store(tmp_path)
    store.create_run("run-1", RunSpec())
    with pytest.raises(KeyError):
        store.review("run-1", "missing", "confirmed", "")
    with pytest.raises(ValueError):
        store.review("run-1", "missing", "invented", "")


def test_each_run_owns_its_review_and_control_label(tmp_path: Path) -> None:
    store = Store(tmp_path)
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo is not None
    for run_id in ["first", "second"]:
        store.create_run(run_id, RunSpec())
        store.save_photos(run_id, [photo])
    store.review("first", photo.id, "confirmed", "Visible in crop")
    assert store.photos("second")[0]["review_status"] == "unreviewed"
