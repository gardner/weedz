"""A study's definition is recorded, checked against the screening code, and versioned."""

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from weedz.discovery.records import RunSpec
from weedz.discovery.store import Store
from weedz.discovery.study import (
    LIMITS,
    Budget,
    StudyDefinition,
    StudyEdit,
    budget_use,
    differences,
    open_decisions,
)
from weedz.discovery.study_store import (
    StaleVersion,
    link_study,
    run_study,
    save_version,
    studies,
    versions,
)


def definition(**fields: Any) -> dict[str, Any]:
    return {
        "question": "Which overlooked old man's beard sites would DOC visit?",
        "partner": "Example Biosecurity Team",
        "people": [{"role": "coordinator", "name": "Ana"}],
        "regions": [{"name": "Nelson", "rationale": "Partner's area"}],
        "watchlist": [{"species": "Clematis vitalba", "rationale": "High management value"}],
    } | fields


def edit(author: str = "Ana", base: int = 0, **fields: Any) -> StudyEdit:
    return StudyEdit(
        definition=StudyDefinition.model_validate(definition(**fields)),
        author=author,
        base_version=base,
    )


def test_an_empty_study_is_provisional_and_every_decision_is_open() -> None:
    study = StudyDefinition()
    assert study.status == "provisional"
    decisions = open_decisions(study)
    assert "Discovery question" in decisions
    assert "Partner" in decisions
    assert "Review budget" in decisions
    assert all(f"Success limit: {name}" in decisions for name, _, _ in LIMITS.values())


def test_a_recorded_decision_is_no_longer_open() -> None:
    study = StudyDefinition.model_validate(
        definition(limits={"coverage": {"value": 80}}, review_budget={"hours": 40})
    )
    decisions = open_decisions(study)
    assert "Discovery question" not in decisions
    assert "Review budget" not in decisions
    assert "Success limit: Coverage and review usability" not in decisions
    assert "Success limit: Useful incidental yield" in decisions


def test_an_agreed_study_needs_a_question_and_a_partner() -> None:
    with pytest.raises(ValidationError, match="question and a partner"):
        StudyDefinition.model_validate(definition(status="agreed", partner=" "))
    assert StudyDefinition.model_validate(definition(status="agreed")).status == "agreed"


def test_a_species_the_screening_does_not_cover_must_be_marked_not_yet_screened() -> None:
    with pytest.raises(ValidationError, match="not in the screening watchlist"):
        StudyDefinition.model_validate(definition(watchlist=[{"species": "Rheum rhabarbarum"}]))
    study = StudyDefinition.model_validate(
        definition(watchlist=[{"species": "Gunnera tinctoria", "screened": False}])
    )
    assert study.watchlist[0].screened is False
    with pytest.raises(ValidationError, match="is screened"):
        StudyDefinition.model_validate(
            definition(watchlist=[{"species": "Clematis vitalba", "screened": False}])
        )


def test_regions_and_lookalikes_are_checked_against_the_code_too() -> None:
    with pytest.raises(ValidationError, match="not a screened region"):
        StudyDefinition.model_validate(definition(regions=[{"name": "Marlborough"}]))
    with pytest.raises(ValidationError, match="not a declared lookalike"):
        StudyDefinition.model_validate(
            definition(lookalikes=[{"taxon": "Clematis montana", "rationale": "Garden"}])
        )
    study = StudyDefinition.model_validate(
        definition(regions=[{"name": "Marlborough", "screened": False}])
    )
    assert study.regions[0].name == "Marlborough"


def test_a_name_appears_once_and_a_period_is_ordered() -> None:
    twice = [{"species": "Clematis vitalba"}, {"species": "Clematis vitalba"}]
    with pytest.raises(ValidationError, match="more than once"):
        StudyDefinition.model_validate(definition(watchlist=twice))
    with pytest.raises(ValidationError, match="start on or before"):
        StudyDefinition.model_validate(
            definition(period_start="2020-01-01", period_end="2019-01-01")
        )


def test_limits_are_known_measures_with_bounded_values() -> None:
    with pytest.raises(ValidationError, match="Unknown outcome measure"):
        StudyDefinition.model_validate(definition(limits={"accuracy": {"value": 1}}))
    with pytest.raises(ValidationError, match="percentage"):
        StudyDefinition.model_validate(definition(limits={"coverage": {"value": 120}}))
    with pytest.raises(ValidationError):
        StudyDefinition.model_validate(definition(limits={"coverage": {"value": -1}}))


def test_differences_name_every_gap_between_the_study_and_the_screening() -> None:
    study = StudyDefinition.model_validate(
        definition(
            watchlist=[
                {"species": "Clematis vitalba"},
                {"species": "Gunnera tinctoria", "screened": False},
            ],
            lookalikes=[{"taxon": "Clematis paniculata", "rationale": "Native, flowers alike"}],
            period_start="2015-01-01",
            period_end="2020-12-31",
        )
    )
    notes = differences(study, RunSpec(after=date(2010, 1, 1), before=date(2024, 12, 31)))
    assert any("Cortaderia selloana" in note and "screened" in note for note in notes)
    assert any("Gunnera tinctoria" in note and "not yet screened" in note for note in notes)
    assert any("Clematis forsteri" in note and "no rationale" in note for note in notes)
    assert not any("Clematis paniculata" in note for note in notes)
    assert any("Tasman" in note for note in notes)
    assert any("2010-01-01" in note and "outside" in note for note in notes)
    assert not any("outside" in note for note in differences(study, None))


def test_budget_use_is_a_lower_bound_while_work_is_untimed() -> None:
    use = budget_use(Budget(hours=2, photos=10), minutes=90, untimed=1, photos=12)
    assert use["hours"] == {
        "budget": 2,
        "used": 1.5,
        "lower_bound": True,
        "state": "within so far",
    }
    assert use["photos"] == {"budget": 10, "used": 12, "lower_bound": False, "state": "spent"}
    unset = budget_use(Budget(), minutes=0, untimed=0, photos=0)
    assert unset["hours"]["state"] == unset["photos"]["state"] == "not set"
    assert budget_use(Budget(hours=1), minutes=60, untimed=3, photos=0)["hours"]["state"] == (
        "spent"
    )


def test_versions_are_appended_with_author_and_a_stale_edit_is_refused(tmp_path: Path) -> None:
    store = Store(tmp_path)
    created = save_version(store, None, edit())
    assert created["version"] == 1
    study_id = created["id"]
    assert save_version(store, study_id, edit("Ben", 1, partner="Partner B"))["version"] == 2
    with pytest.raises(StaleVersion):
        save_version(store, study_id, edit("Cat", 1, partner="Partner C"))
    history = versions(store, study_id)
    assert [(item["version"], item["author"]) for item in history] == [(1, "Ana"), (2, "Ben")]
    assert history[-1]["definition"]["partner"] == "Partner B"
    assert history[0]["definition"]["partner"] == "Example Biosecurity Team"
    assert history[0]["created_at"]
    with pytest.raises(StaleVersion):
        save_version(store, None, edit(base=3))


def test_runs_link_to_a_study_and_the_latest_link_stands(tmp_path: Path) -> None:
    store = Store(tmp_path)
    for run_id in ("run", "other"):
        store.create_run(run_id, RunSpec())
    assert run_study(store, "run") is None
    first = save_version(store, None, edit())["id"]
    second = save_version(store, None, edit(question="Second question"))["id"]
    link_study(store, "run", first, "Ana")
    link_study(store, "other", first, "Ana")
    link_study(store, "run", second, "Ben")
    linked = run_study(store, "run")
    assert linked is not None
    assert (linked["id"], linked["version"]) == (second, 1)
    assert linked["definition"]["question"] == "Second question"
    assert linked["linked_by"] == "Ben"
    assert "Partner" not in linked["open_decisions"]
    assert isinstance(linked["differences"], list)
    listed = {item["id"]: item for item in studies(store)}
    assert listed[first]["runs"] == ["other"]
    assert listed[second]["runs"] == ["run"]
    with pytest.raises(KeyError):
        link_study(store, "run", "study-missing", "Ana")


def test_a_stored_study_still_reads_after_the_screening_code_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path)
    store.create_run("run", RunSpec())
    link_study(store, "run", save_version(store, None, edit())["id"], "Ana")
    monkeypatch.setattr("weedz.discovery.study.SPECIES", {"Ulex europaeus": "Gorse"})
    linked = run_study(store, "run")
    assert linked is not None
    assert any("Clematis vitalba" in note and "no longer" in note for note in linked["differences"])
    with pytest.raises(ValidationError, match="not in the screening watchlist"):
        StudyDefinition.model_validate(definition())
