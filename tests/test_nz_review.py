"""Review preparation does not turn source subjects into human-labelled gold."""

from weedz.labelled.nz_review import eligible


def row(observation, observer):
    return {"id": observation, "user": {"login": observer, "id": observer}}


def test_previous_observation_and_observer_groups_are_excluded():
    assert not eligible(row(1, "new"), {1}, {"old"}, set(), set())
    assert not eligible(row(2, "old"), {1}, {"old"}, set(), set())
    assert eligible(row(2, "new"), {1}, {"old"}, set(), set())


def test_same_observation_and_observer_cannot_be_counted_independent():
    assert not eligible(row(2, "new"), set(), set(), {2}, set())
    assert not eligible(row(2, "new"), set(), set(), set(), {"new"})
