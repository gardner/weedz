"""The novelty measure reports reviewers' judged levels beside the computed comparison."""

from typing import Any

from test_outcomes import SNAPSHOT, export, measure, photo

from weedz.discovery.outcome_report import to_markdown
from weedz.discovery.outcomes import NOT_YET, PARTIAL, outcomes

SHA = "a" * 64
REFERENCES = SNAPSHOT | {"snapshot_sha256": SHA}
NONE = {"photos": 0, "site_visits": 0, "ungrouped_photos": 0}


def judged(*claims: tuple[str, str, str], snapshot: str | None = SHA) -> dict[str, Any]:
    """Standing novelty judgements from (reviewer, value, note) claims."""
    standing = {
        reviewer: {"value": value, "note": note, "reference_snapshot": snapshot}
        for reviewer, value, note in claims
    }
    return {"judgements": {"novelty": standing}}


def confirmed(pid: str, group: str | None, *claims: tuple[str, str, str], **fields: Any):
    return photo(pid, group, review_status="confirmed", **fields) | judged(*claims)


def novelty(photos: list[dict[str, Any]], references: Any = REFERENCES) -> dict[str, Any]:
    return measure(outcomes(export(photos, references=references)), "novel_or_earlier_evidence")


def test_judged_levels_are_tallied_as_site_visits_beside_the_comparison() -> None:
    photos = [
        confirmed("a", "v1", ("Ana", "new_in_photo", "")),
        confirmed("b", "v1", ("Ana", "new_in_photo", "")),
        confirmed("c", "v2", ("Ana", "already_recorded", "")),
        confirmed("d", None),
    ]
    levels = novelty(photos)["evidence"]["judged_novelty"]
    assert levels["new_in_photo"] == {"photos": 2, "site_visits": 1, "ungrouped_photos": 0}
    assert levels["already_recorded"]["site_visits"] == 1
    assert levels["unassessed"] == {"photos": 1, "site_visits": 0, "ungrouped_photos": 1}
    assert levels["verified_new_locality"] == NONE
    assert levels["disputed"] == NONE


def test_reviewers_who_disagree_are_disputed_never_a_level() -> None:
    photos = [
        confirmed(
            "a",
            "v1",
            ("Ana", "verified_new_locality", "Checked on site"),
            ("Bo", "new_in_photo", ""),
        )
    ]
    evidence = novelty(photos)["evidence"]
    assert evidence["judged_novelty"]["disputed"]["site_visits"] == 1
    assert evidence["judged_novelty"]["verified_new_locality"] == NONE
    assert evidence["judged_novelty"]["new_in_photo"] == NONE
    assert evidence["verified_new_localities"] == []


def test_reviewers_who_agree_are_one_level() -> None:
    photos = [confirmed("a", "v1", ("Ana", "new_in_photo", ""), ("Bo", "new_in_photo", "x"))]
    assert novelty(photos)["evidence"]["judged_novelty"]["new_in_photo"]["photos"] == 1


def test_only_a_noted_verification_is_a_new_locality_and_its_note_is_shown() -> None:
    note = "DOC ranger checked the site on 2026-10-02"
    photos = [
        confirmed("a", "v1", ("Ana", "verified_new_locality", note)),
        confirmed("b", "v2", ("Bo", "verified_new_locality", "  ")),
    ]
    evidence = novelty(photos)["evidence"]
    assert evidence["judged_novelty"]["verified_new_locality"]["photos"] == 1
    assert evidence["judged_novelty"]["unassessed"]["photos"] == 1
    assert evidence["verified_new_localities"] == [
        {"photo_id": "a", "reviewer": "Ana", "note": note}
    ]
    text = to_markdown(outcomes(export(photos, references=REFERENCES)))
    assert f"verified_new_localities: photo_id: a; reviewer: Ana; note: {note}" in text


def test_recorded_watchlist_plants_are_judged_by_their_own_judgements() -> None:
    plant = {"id": 7, "kind": "addition", "species": "Ulex europaeus", "effort_seconds": 5}
    plant |= judged(("Ana", "verified_new_locality", "Herbarium specimen WELT 123"))
    photos = [photo("a", "v1", review_status="rejected", findings=[plant])]
    evidence = novelty(photos)["evidence"]
    assert evidence["judged_novelty"]["verified_new_locality"]["photos"] == 1
    assert evidence["verified_new_localities"][0]["finding_id"] == 7


def test_judgements_on_unconfirmed_suggestions_are_not_counted() -> None:
    photos = [photo("a", "v1", review_status="uncertain") | judged(("Ana", "new_in_photo", ""))]
    evidence = novelty(photos)["evidence"]
    assert evidence["judged_novelty"]["new_in_photo"] == NONE


def test_record_relative_claims_on_another_snapshot_are_flagged() -> None:
    far = {"Ulex europaeus": {"comparable": True, "within_radius": 0, "radius_m": 5000.0}}
    current = confirmed("a", "v1", ("Ana", "absent_from_references", ""))
    older = photo("b", "v2", review_status="confirmed") | judged(
        ("Ana", "absent_from_references", ""), snapshot="b" * 64
    )
    for item in (current, older):
        item["reference_comparison"] = far
    evidence = novelty([current, older])["evidence"]
    assert evidence["judged_novelty"]["absent_from_references"]["photos"] == 2
    assert evidence["record_relative_judged_against_another_snapshot"]["photos"] == 1


def test_judged_novelty_is_reported_without_a_reference_snapshot() -> None:
    photos = [confirmed("a", "v1", ("Ana", "new_in_photo", ""))]
    novel = novelty(photos, references=None)
    assert novel["status"] == PARTIAL
    assert novel["value"] is None
    assert novel["evidence"]["judged_novelty"]["new_in_photo"]["photos"] == 1
    assert "no reference snapshot" in novel["reason"].lower()
    assert "reviewer" in novel["reason"].lower()


def test_without_a_snapshot_or_any_judgement_novelty_is_not_yet_measurable() -> None:
    novel = novelty([confirmed("a", "v1")], references=None)
    assert novel["status"] == NOT_YET
    assert novel["evidence"]["judged_novelty"]["unassessed"]["photos"] == 1


def test_the_reason_never_calls_judged_levels_a_first_occurrence() -> None:
    far = {"Ulex europaeus": {"comparable": True, "within_radius": 0, "radius_m": 5000.0}}
    photos = [confirmed("a", "v1", ("Ana", "new_in_photo", ""), reference_comparison=far)]
    novel = novelty(photos)
    assert novel["status"] == PARTIAL
    assert novel["value"]["photos"] == 1
    assert "(#25)" not in novel["reason"]
    assert "only a noted verified_new_locality" in novel["reason"].lower()
    assert "disputed" in novel["reason"].lower()


def test_judged_levels_render_in_the_markdown_report() -> None:
    photos = [confirmed("a", "v1", ("Ana", "new_in_photo", ""))]
    text = to_markdown(outcomes(export(photos, references=REFERENCES)))
    assert "judged_novelty: " in text
    assert "new_in_photo: 1 site visit + 0 ungrouped photos (1 photo)" in text
