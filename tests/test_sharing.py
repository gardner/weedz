"""One rights-and-privacy policy decides what may leave the project, per photo and use."""

from typing import Any

import pytest

from weedz.discovery.sharing import (
    ADMITTED,
    image_use,
    location,
    not_admitted,
    shareable_export,
    terms,
)


def photo(**fields: Any) -> dict[str, Any]:
    return {
        "id": "inat-1-2",
        "source_url": "https://www.inaturalist.org/observations/1",
        "attribution": "(c) Example observer, some rights reserved (CC BY-NC)",
        "observer": "observer",
        "photo_license": "cc-by-nc",
        "observation_license": "cc-by",
        "latitude": -41.27,
        "longitude": 173.28,
        "positional_accuracy_m": 12.0,
        "coordinate_status": "public",
    } | fields


def test_only_cc0_cc_by_and_cc_by_nc_are_admitted() -> None:
    assert set(ADMITTED) == {"cc0", "cc-by", "cc-by-nc"}


@pytest.mark.parametrize("licence", ["cc0", "cc-by", "cc-by-nc"])
def test_an_admitted_photo_is_shown_in_review_and_included_when_shared(licence: str) -> None:
    item = photo(photo_license=licence)
    assert image_use(item, "review").action == "show"
    shared = image_use(item, "share")
    assert shared.action == "include"
    assert shared.reason == ADMITTED[licence]


def test_non_commercial_terms_travel_with_a_cc_by_nc_photo() -> None:
    assert "non-commercial" in image_use(photo(), "share").reason


@pytest.mark.parametrize(
    ("licence", "named"),
    [
        ("cc-by-nd", "no-derivatives"),
        ("cc-by-nc-nd", "no-derivatives"),
        ("cc-by-sa", "share-alike"),
        ("cc-by-nc-sa", "share-alike"),
        (None, "all rights reserved"),
        ("", "all rights reserved"),
        ("something-new", "something-new"),
    ],
)
def test_each_other_licence_is_link_only_with_its_own_reason(
    licence: str | None, named: str
) -> None:
    item = photo(photo_license=licence)
    for use in ("review", "share"):
        decided = image_use(item, use)
        assert decided.action == "link"
        assert named in decided.reason.lower()
    assert named in not_admitted(licence).lower()


def test_terms_carry_attribution_and_both_licences_conditions() -> None:
    carried = terms(photo())
    assert carried["attribution"].startswith("(c) Example observer")
    assert carried["observer"] == "observer"
    assert carried["source_url"] == "https://www.inaturalist.org/observations/1"
    assert carried["photo_licence"] == "cc-by-nc"
    assert "non-commercial" in carried["photo_terms"]
    assert carried["observation_licence"] == "cc-by"
    assert "credit" in carried["observation_terms"].lower()
    assert carried["non_commercial"] is True
    assert terms(photo(photo_license="cc-by"))["non_commercial"] is False
    assert terms(photo(photo_license="cc0", observation_license="cc-by-nc"))["non_commercial"]


def test_a_public_point_with_known_accuracy_leaves_with_its_accuracy() -> None:
    for use in ("review", "share"):
        shared = location(photo(), use)
        assert (shared.latitude, shared.longitude) == (-41.27, 173.28)
        assert shared.accuracy_m == 12.0
        assert shared.withheld == ""


def test_an_obscured_point_never_leaves_for_any_use() -> None:
    for use in ("review", "share"):
        shared = location(photo(coordinate_status="obscured"), use)
        assert (shared.latitude, shared.longitude) == (None, None)
        assert shared.status == "obscured"
        assert "obscured" in shared.withheld.lower()


def test_a_public_point_of_unknown_accuracy_is_shown_locally_but_not_shared() -> None:
    item = photo(positional_accuracy_m=None)
    assert location(item, "review").latitude == -41.27
    shared = location(item, "share")
    assert shared.latitude is None and shared.longitude is None
    assert "accuracy" in shared.withheld.lower()


def test_a_location_under_a_non_admitted_observation_licence_is_not_shared() -> None:
    shared = location(photo(observation_license="cc-by-nd"), "share")
    assert shared.latitude is None
    assert "observation licence" in shared.withheld.lower()


def test_a_missing_location_stays_missing() -> None:
    shared = location(photo(latitude=None, longitude=None, coordinate_status="missing"), "share")
    assert (shared.latitude, shared.longitude, shared.status) == (None, None, "missing")


def test_the_shareable_export_withholds_points_and_carries_terms() -> None:
    full = {
        "schema": 1,
        "photos": [photo(id="public"), photo(id="hidden", coordinate_status="obscured")],
    }
    shared = shareable_export(full)
    public, hidden = shared["photos"]
    assert (public["latitude"], public["longitude"]) == (-41.27, 173.28)
    assert (hidden["latitude"], hidden["longitude"]) == (None, None)
    assert hidden["coordinate_status"] == "obscured"
    assert hidden["sharing"]["location"]["withheld"]
    assert public["sharing"]["image"] == {"action": "include", "reason": ADMITTED["cc-by-nc"]}
    assert public["sharing"]["terms"]["non_commercial"] is True
    assert any("on anyone's behalf" in rule for rule in shared["sharing"])
    # The full record is not changed in place.
    assert full["photos"][1]["latitude"] == -41.27


def test_a_withheld_point_takes_its_search_area_centre_along() -> None:
    area = {"status": "searchable", "centre": (-41.27, 173.28), "radius_m": 112.0}
    item = photo(observation_license="cc-by-nd", limits={"search_area": area, "dates": {}})
    shared = shareable_export({"photos": [item]})["photos"][0]
    assert shared["limits"]["search_area"]["centre"] is None
    assert shared["limits"]["search_area"]["radius_m"] is None
    assert shared["limits"]["dates"] == {}
    kept = shareable_export({"photos": [photo(limits={"search_area": area})]})["photos"][0]
    assert kept["limits"]["search_area"]["centre"] == (-41.27, 173.28)
