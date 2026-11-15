"""A worker policy restricts both observation requests and admitted source records."""

import pytest
from test_discovery import observation

from weedz.discovery.source import Inaturalist, photo_from_observation

STRICT = frozenset({"cc0", "cc-by"})


def test_worker_policy_rejects_noncommercial_metadata_even_if_api_returns_it():
    raw = observation()
    assert photo_from_observation(raw, "Nelson", "incidental") is not None
    assert photo_from_observation(raw, "Nelson", "incidental", allowed_licences=STRICT) is None
    raw["license_code"] = "cc-by"
    assert photo_from_observation(raw, "Nelson", "incidental", allowed_licences=STRICT) is None
    raw["photos"][0]["license_code"] = "cc-by"
    assert photo_from_observation(raw, "Nelson", "incidental", allowed_licences=STRICT) is not None


def test_worker_policy_must_be_a_nonempty_subset_of_admitted_licences(tmp_path):
    for policy in [frozenset(), frozenset({"all-rights-reserved"})]:
        with pytest.raises(ValueError, match="licence"):
            Inaturalist(tmp_path, allowed_photo_licences=policy)


def test_trusted_policy_is_sent_to_both_observation_and_photo_queries(tmp_path, monkeypatch):
    from weedz.discovery.records import RunSpec

    client = Inaturalist(tmp_path, allowed_photo_licences=STRICT)
    queries = []

    def query(_snapshot, params):
        queries.append(params)
        return {"response": {"results": []}}

    monkeypatch.setattr(client, "query", query)
    try:
        client.collect("run", RunSpec(sampling="recent", controls_per_species=0))
    finally:
        client.close()
    assert queries
    assert all(
        row["license"] == "cc-by,cc0" and row["photo_license"] == "cc-by,cc0" for row in queries
    )


def test_download_refuses_metadata_outside_worker_policy_before_any_write(tmp_path):
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo
    client = Inaturalist(tmp_path, allowed_photo_licences=STRICT)
    try:
        with pytest.raises(ValueError, match="licence policy"):
            client.image(photo)
    finally:
        client.close()
    assert not (tmp_path / "images").exists()
