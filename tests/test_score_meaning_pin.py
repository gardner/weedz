"""Each run keeps the score meaning it was screened under, even after a new version."""

import hashlib
from pathlib import Path

import pytest
from test_discovery import observation
from test_score_meaning import model

from weedz.discovery import score_meaning as meanings
from weedz.discovery.activities import Activities
from weedz.discovery.records import RunSpec
from weedz.discovery.score_meaning import pin_meaning, score_meaning
from weedz.discovery.source import photo_from_observation

FIRST = "bioclip-2/ranking-4/meaning-1"
SECOND = "bioclip-2/ranking-4/meaning-2"


@pytest.fixture
def second_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """A later declaration for the same configuration, e.g. once an operating point exists."""
    later = meanings.DECLARED[FIRST] | {"id": SECOND, "meaning_version": 2}
    monkeypatch.setitem(meanings.DECLARED, SECOND, later)
    monkeypatch.setitem(meanings.CURRENT, ("bioclip-2", 4), SECOND)


def test_a_new_run_is_pinned_to_the_current_declaration() -> None:
    assert pin_meaning(None, model()) == model() | {"score_meaning": FIRST}


def test_an_undeclared_configuration_is_pinned_as_undeclared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved = pin_meaning(None, model(ranking=5))
    assert saved["score_meaning"] is None
    later = meanings.DECLARED[FIRST] | {
        "id": "bioclip-2/ranking-5/meaning-1",
        "ranking_revision": 5,
    }
    monkeypatch.setitem(meanings.DECLARED, later["id"], later)
    assert score_meaning(later_model := model(ranking=5))["id"] == later["id"]
    assert score_meaning(saved)["declared"] is False, "a later declaration cannot claim it"
    assert pin_meaning(saved, later_model)["score_meaning"] is None, "a retry keeps it"


@pytest.mark.usefixtures("second_version")
def test_a_resumed_run_keeps_its_pinned_meaning() -> None:
    saved = model() | {"score_meaning": FIRST}
    assert pin_meaning(saved, model())["score_meaning"] == FIRST
    assert score_meaning(saved)["id"] == FIRST
    assert score_meaning(pin_meaning(None, model()))["id"] == SECOND


@pytest.mark.usefixtures("second_version")
def test_runs_screened_before_pinning_keep_the_first_declaration() -> None:
    assert score_meaning(model())["id"] == FIRST
    assert "score_meaning" not in pin_meaning(model(), model())


def test_a_changed_configuration_is_still_refused() -> None:
    with pytest.raises(ValueError, match="configuration changed"):
        pin_meaning(model() | {"score_meaning": FIRST}, model(ranking=5))


def test_a_pin_that_does_not_match_the_configuration_is_not_trusted() -> None:
    saved = model("bioclip") | {"score_meaning": FIRST}
    assert score_meaning(saved)["declared"] is False
    assert score_meaning(model() | {"score_meaning": "unknown"})["declared"] is False


def test_screening_records_the_pinned_meaning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    activities = Activities(tmp_path)
    activities.store.create_run("run", RunSpec())
    photo = photo_from_observation(observation(), "Nelson", "incidental")
    assert photo is not None
    photo.image_path = "image.jpg"
    (tmp_path / photo.image_path).write_bytes(b"test image")
    photo.sha256 = hashlib.sha256(b"test image").hexdigest()
    activities.store.save_photos("run", [photo])

    class FakeScreener:
        metadata = model()

        def screen(self, _path: Path, _subject: str | None = None) -> dict:
            return {"margin": 0.0}

    activities.screeners[RunSpec().model] = FakeScreener()
    monkeypatch.setattr("weedz.discovery.activities.activity.heartbeat", lambda *_: None)
    activities.screen_photos({"run_id": "run"})
    assert activities.store.runs()[0]["model"]["score_meaning"] == FIRST
    activities.screen_photos({"run_id": "run"})  # a retry resumes under the same pin
    assert activities.store.runs()[0]["model"]["score_meaning"] == FIRST
