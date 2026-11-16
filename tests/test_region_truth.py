"""Only independent present geometry enters localisation denominators."""

import pytest

from weedz.contract import Annotation
from weedz.region_evaluation.truth import labelled_boxes


def annotation(**fields) -> Annotation:
    return Annotation.model_validate(
        {
            "id": "source:1",
            "supervision": "box",
            "box": [1, 2, 4, 6],
            "category": "weed",
            "label": "present",
            "origin": "source",
        }
        | fields
    )


def test_source_box_is_retained_with_its_actual_label_space() -> None:
    truth = labelled_boxes([annotation()], size=(10, 10))
    assert len(truth) == 1
    assert truth[0].box == (1, 2, 4, 6)
    assert truth[0].taxon is None
    assert truth[0].category == "weed"
    assert truth[0].origin == "source"


def test_model_unknown_absent_and_rejected_boxes_are_not_positive_truth() -> None:
    labels = [
        annotation(id="model:1", origin="model", model="sam"),
        annotation(id="source:unknown", label="unknown"),
        annotation(id="source:absent", label="absent"),
        annotation(id="source:rejected", review="rejected"),
    ]
    assert labelled_boxes(labels, size=(10, 10)) == ()


def test_source_image_label_does_not_become_a_region() -> None:
    label = annotation(supervision="image_class", box=None)
    assert labelled_boxes([label], size=(10, 10)) == ()


def test_duplicate_ids_and_out_of_frame_geometry_refused() -> None:
    with pytest.raises(ValueError, match="Duplicate"):
        labelled_boxes([annotation(), annotation()], size=(10, 10))
    with pytest.raises(ValueError, match="frame"):
        labelled_boxes([annotation(box=[1, 2, 11, 6])], size=(10, 10))


def test_mask_requires_explicit_separate_mask_evaluation() -> None:
    label = annotation(
        supervision="dense_mask", box=None, mask_uri="truth.png", mask_sha256="a" * 64
    )
    assert labelled_boxes([label], size=(10, 10)) == ()


def test_reviewer_drafts_are_not_evaluation_truth_before_acceptance() -> None:
    draft = annotation(origin="reviewer", author="reviewer:a")
    assert labelled_boxes([draft], size=(10, 10)) == ()
    accepted = annotation(origin="reviewer", author="reviewer:a", review="accepted")
    assert len(labelled_boxes([accepted], size=(10, 10))) == 1
