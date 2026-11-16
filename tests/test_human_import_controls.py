"""Scoped completeness and explicit decisions are separate from old presence controls."""

import pytest

from weedz.annotation.gold_config import gold_config
from weedz.annotation.import_controls import decisions
from weedz.annotation.label_studio import label_config


def choice(name, values):
    return {"from_name": name, "to_name": "image", "type": "choices", "value": {"choices": values}}


def test_review_and_scope_are_explicit():
    rows = [
        choice("completeness_task", ["detection"]),
        choice("review_status", ["accepted"]),
        choice("completeness_status", ["exhaustive"]),
        choice("completeness_taxa", ["Ulex europaeus"]),
    ]
    result = decisions(rows, {"Ulex europaeus"}, set())
    assert result.review == "accepted" and result.status == "exhaustive"
    assert result.taxa == ("Ulex europaeus",)
    with pytest.raises(ValueError):
        decisions(rows[:2], {"Ulex europaeus"}, set())
    with pytest.raises(ValueError):
        decisions(rows, {"different taxon"}, set())
    with pytest.raises(ValueError):
        decisions(rows + [rows[0]], {"Ulex europaeus"}, set())


def test_old_answers_are_not_a_review_scope():
    with pytest.raises(ValueError):
        decisions([choice("watchlist_presence", ["No watchlist plant visible"])], {"Ulex"}, set())


def test_optional_configuration_escapes_source_labels_without_changing_default():
    original = label_config("assisted")
    xml = gold_config(("Clematis & friends",), ("other <plant>",))
    assert 'value="Clematis &amp; friends"' in xml
    assert 'value="other &lt;plant&gt;"' in xml
    assert 'name="regions"' in xml and 'name="review_boxes"' in xml
    assert label_config("assisted") == original
    assert "completeness_status" not in original
