"""A logical pipeline version ignores corpus notes, never weights or inference settings."""

from copy import deepcopy

import pytest

from weedz.annotation.semantic import shared_regional_version


def metadata():
    classifier = {
        "repository": "repo",
        "revision": "revision",
        "weights_sha256": "a" * 64,
        "labels_sha256": "b" * 64,
        "class_count": 7806,
        "preprocessing": {"input_size": [3, 518, 518], "mean": [0.1, 0.2, 0.3]},
        "precision": "float32",
        "timm": "1.0",
        "torch": "2.0",
        "score_kind": "closed_set_softmax_uncalibrated",
    }
    proposer = {
        "model": "SAM2.1 Hiera tiny",
        "code_revision": "sam-code",
        "checkpoint_sha256": "c" * 64,
        "proposal_config": {
            "max_side": 768,
            "points_per_side": 8,
            "points_per_batch": 8,
            "max_proposals": 12,
            "min_area": 16,
            "context_fraction": 0.25,
        },
        "mask_filter": {
            "predicted_iou_threshold": 0.8,
            "stability_threshold": 0.95,
            "box_nms_threshold": 0.7,
            "mask_threshold": 0.0,
        },
        "transforms_revision": 1,
        "class_agnostic": True,
        "crop_layers": 0,
        "postprocessing": False,
        "torch": "2.0+cu",
        "torchvision": "0.2",
        "pillow": "13",
        "numpy": "2",
    }
    return classifier, proposer


def test_same_logical_method_has_same_version_across_metadata_packaging():
    classifier, proposer = metadata()
    old = {"classifier": classifier, "proposer": dict(proposer, config=proposer["proposal_config"])}
    bulk = dict(
        classifier,
        proposer=dict(proposer, config="architecture.yaml"),
        input_policy="Different corpus notes, same normalized pixels",
    )
    assert shared_regional_version(old) == shared_regional_version(bulk)


def test_changed_model_or_dense_grid_is_a_different_pipeline():
    classifier, proposer = metadata()
    original = {"classifier": classifier, "proposer": proposer}
    dense = deepcopy(original)
    dense["proposer"]["proposal_config"]["points_per_side"] = 32
    assert (
        shared_regional_version(dense)["model_version"]
        != shared_regional_version(original)["model_version"]
    )
    changed = deepcopy(original)
    changed["classifier"]["preprocessing"]["mean"][0] = 0.5
    assert shared_regional_version(changed)["sha256"] != shared_regional_version(original)["sha256"]


def test_incomplete_semantics_cannot_receive_a_shared_version():
    with pytest.raises(ValueError, match="semantic"):
        shared_regional_version({"revision": "not enough"})
