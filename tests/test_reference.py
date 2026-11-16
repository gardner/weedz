"""Each reviewed example states what it is and which uses its evidence and rights allow."""

from typing import Any

import pytest

from weedz.contract import Annotation, Sample
from weedz.reference import collection, examples, licence_code, standing


def note(**fields: Any) -> dict[str, Any]:
    return {
        "id": "a1",
        "supervision": "image_class",
        "taxon": "Ulex europaeus",
        "label": "present",
        "origin": "source",
    } | fields


def sample(*notes: dict[str, Any], **fields: Any) -> Sample:
    record = {
        "id": "test:1",
        "source": "test",
        "source_id": "1",
        "snapshot": "rev-1",
        "rights": {
            "media_license": "cc-by",
            "metadata_license": "cc0",
            "attribution": "(c) Ana, CC BY",
            "license_source": "https://example.org/1",
        },
        "media": {"uri": "https://example.org/1.jpg"},
        "geography": {"latitude": -41.3, "longitude": 173.2, "uncertainty_m": 10},
        "tasks": ["inference"],
        "annotations": list(notes) or [note()],
    } | fields
    return Sample.model_validate(record)


def only(record: Sample) -> dict[str, Any]:
    (example,) = examples([record])
    return example


def reasons(example: dict[str, Any]) -> dict[str, str]:
    return {use: verdict["reason"] for use, verdict in example["uses"].items()}


def eligible(example: dict[str, Any]) -> set[str]:
    return {use for use, verdict in example["uses"].items() if verdict["eligible"]}


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({}, "original"),
        ({"review": "accepted"}, "original"),
        ({"review": "rejected"}, "unsuitable"),
        ({"review": "uncertain"}, "unresolved"),
        ({"origin": "reviewer", "author": "Carol"}, "unreviewed"),
        ({"origin": "reviewer", "author": "Carol", "review": "accepted"}, "accepted"),
        ({"origin": "reviewer", "author": "Carol", "review": "rejected"}, "unsuitable"),
        ({"origin": "model", "model": "bioclip-2"}, "unreviewed"),
        ({"origin": "model", "model": "bioclip-2", "review": "accepted"}, "accepted"),
        ({"origin": "model", "model": "bioclip-2", "review": "uncertain"}, "unresolved"),
    ],
)
def test_each_example_has_a_standing(fields: dict[str, Any], expected: str) -> None:
    assert standing(Annotation.model_validate(note(**fields))) == expected


def test_an_original_source_label_is_eligible_for_every_use() -> None:
    example = only(sample())
    assert example["standing"] == "original"
    assert eligible(example) == {"training", "evaluation", "sharing"}
    assert set(reasons(example).values()) == {""}


def test_a_correction_accepted_by_others_is_evaluation_evidence() -> None:
    accepted = note(origin="reviewer", author="Carol", reviewers=["Ana", "Ben"], review="accepted")
    example = only(sample(accepted))
    assert (example["standing"], example["author"], example["reviewers"]) == (
        "accepted",
        "Carol",
        ["Ana", "Ben"],
    )
    assert eligible(example) == {"training", "evaluation", "sharing"}


def test_a_label_accepted_only_by_its_author_is_not_evaluation_evidence() -> None:
    own = note(origin="reviewer", author="Carol", reviewers=["Carol"], review="accepted")
    example = only(sample(own))
    assert eligible(example) == {"training", "sharing"}
    assert "other than its author" in reasons(example)["evaluation"]


def test_an_unreviewed_finding_is_retained_but_has_no_reference_use() -> None:
    example = only(sample(note(origin="reviewer", author="Carol")))
    assert example["standing"] == "unreviewed"
    assert eligible(example) == set()
    assert all("not accepted" in reason for reason in reasons(example).values())


def test_an_accepted_suggestion_trains_and_shares_but_never_evaluates() -> None:
    suggestion = note(origin="model", model="bioclip-2", reviewers=["Ana"], review="accepted")
    example = only(sample(suggestion))
    assert example["standing"] == "accepted" and example["origin"] == "model"
    assert eligible(example) == {"training", "sharing"}
    assert "saw the suggestion" in reasons(example)["evaluation"]


def test_an_unreviewed_suggestion_is_a_prediction_for_no_use() -> None:
    example = only(sample(note(origin="model", model="bioclip-2")))
    assert eligible(example) == set()
    assert "prediction" in reasons(example)["training"]


@pytest.mark.parametrize("review", ["rejected", "uncertain"])
def test_rejected_and_unresolved_examples_are_kept_but_used_for_nothing(review: str) -> None:
    example = only(sample(note(origin="reviewer", author="Carol", review=review)))
    assert eligible(example) == set()
    assert all(reasons(example).values())


def test_an_unknown_label_gives_no_use_a_target() -> None:
    example = only(sample(note(label="unknown")))
    assert eligible(example) == set()
    assert "present or absent" in reasons(example)["training"]


@pytest.mark.parametrize(
    ("media", "metadata", "reason"),
    [
        ("cc-by-nd", "cc0", "no-derivatives"),
        ("cc-by", "arr", "all rights reserved"),
        ("cc-by-sa", "cc0", "share-alike"),
    ],
)
def test_sharing_needs_admitted_photo_and_observation_licences(
    media: str, metadata: str, reason: str
) -> None:
    rights = {
        "media_license": media,
        "metadata_license": metadata,
        "attribution": "(c) Ana",
        "license_source": "https://example.org/1",
    }
    example = only(sample(rights=rights))
    assert eligible(example) == {"training", "evaluation"}
    assert reason in reasons(example)["sharing"]


@pytest.mark.parametrize(
    ("text", "code"),
    [("CC-BY-4.0", "cc-by"), ("cc-by-nc", "cc-by-nc"), ("CC0-1.0", "cc0"), ("CC BY 4.0", "cc-by")],
)
def test_versioned_licence_names_are_read_as_policy_codes(text: str, code: str) -> None:
    assert licence_code(text) == code


def test_non_commercial_terms_travel_with_the_example() -> None:
    rights = {
        "media_license": "cc-by-nc",
        "metadata_license": "cc-by",
        "attribution": "(c) Ana, CC BY-NC",
        "license_source": "https://example.org/1",
    }
    example = only(sample(rights=rights))
    assert "sharing" in eligible(example)
    assert example["rights"]["non_commercial"] is True
    assert example["rights"]["attribution"] == "(c) Ana, CC BY-NC"


def test_an_obscured_location_is_withheld_and_no_coordinates_are_carried() -> None:
    hidden = {"latitude": -41.3, "longitude": 173.2, "privacy": "obscured"}
    example = only(sample(geography=hidden))
    assert example["location"] == {
        "shareable": False,
        "reason": "Withheld: the source obscured this location, so its displaced point is "
        "never passed on",
    }
    assert "sharing" in eligible(example)  # the photo and label may still be shared
    assert "-41.3" not in str(example) and "173.2" not in str(example)


def test_a_point_without_its_accuracy_is_withheld_and_a_missing_one_is_said_so() -> None:
    vague = only(sample(geography={"latitude": -41.3, "longitude": 173.2}))
    assert vague["location"]["shareable"] is False
    assert "accuracy" in vague["location"]["reason"]
    assert only(sample(geography=None))["location"] == {
        "shareable": False,
        "reason": "No location was recorded",
    }
    assert only(sample())["location"] == {"shareable": True, "reason": ""}


def test_an_example_keeps_the_original_source_label_and_its_context() -> None:
    record = sample(
        original_label="Turdus merula",
        captured_on="2020-07-04",
        context={"region": "Nelson"},
        view="ground",
    )
    example = only(record)
    assert example["original_label"] == "Turdus merula"
    assert (example["sample_id"], example["annotation_id"], example["source"]) == (
        "test:1",
        "a1",
        "test",
    )
    assert (example["view"], example["season"], example["region"]) == ("ground", "JJA", "Nelson")


def test_the_collection_counts_standings_and_eligibility_with_reasons() -> None:
    rejected = note(id="a2", origin="reviewer", author="Carol", review="rejected")
    result = collection("run", [sample(note(), rejected)])
    assert result["name"] == "run"
    assert result["standings"] == {"original": 1, "unsuitable": 1}
    training = result["uses"]["training"]
    assert training["eligible"] == 1
    assert sum(training["not_eligible"].values()) == 1
    assert len(result["examples"]) == 2
    assert "growth_stage" in result["not_recorded"] and "habitat" in result["not_recorded"]


def test_a_rejected_suggestion_is_not_turned_into_a_negative() -> None:
    rejected = note(origin="model", model="bioclip-2", reviewers=["Ana"], review="rejected")
    example = only(sample(rejected))
    assert (example["standing"], example["label"]) == ("unsuitable", "present")
    assert "not turned into a negative" in reasons(example)["training"]
