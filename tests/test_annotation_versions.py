"""A logical pipeline version ignores corpus notes, never weights or inference settings."""

from copy import deepcopy
from typing import Any

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


def test_invalid_classifier_metadata_is_a_validation_error():
    with pytest.raises(ValueError, match="semantic"):
        shared_regional_version({"classifier": "not metadata"})


def test_recorded_transform_runtime_versions_change_shared_identity():
    classifier, proposer = metadata()
    legacy = {"classifier": classifier, "proposer": proposer}
    recorded = deepcopy(legacy)
    recorded["classifier"].update(pillow="13.0", torchvision="0.30")
    changed = deepcopy(recorded)
    changed["classifier"]["pillow"] = "14.0"
    assert shared_regional_version(recorded)["sha256"] != shared_regional_version(legacy)["sha256"]
    assert shared_regional_version(recorded)["sha256"] != shared_regional_version(changed)["sha256"]


def test_recorded_numerics_change_identity_without_rewriting_historical_semantics():
    classifier, proposer = metadata()
    historical = {"classifier": classifier, "proposer": proposer}
    old = shared_regional_version(historical)
    recorded = deepcopy(historical)
    recorded["classifier"].update(
        numpy="2.5.4",
        math_policy={"cuda_matmul_tf32": False, "cudnn_tf32": False, "autocast": False},
    )
    new = shared_regional_version(recorded)
    assert new["sha256"] != old["sha256"]
    changed = deepcopy(recorded)
    changed["classifier"]["numpy"] = "1.26.4"
    assert shared_regional_version(changed)["sha256"] != new["sha256"]
    changed = deepcopy(recorded)
    changed["classifier"]["math_policy"]["cuda_matmul_tf32"] = True
    assert shared_regional_version(changed)["sha256"] != new["sha256"]
    assert "math_policy" not in old["semantic"]["classifier"]
    assert "numpy" not in old["semantic"]["classifier"]
    assert shared_regional_version(historical) == old


@pytest.mark.parametrize("pins", [{"pillow": "13"}, {"pillow": "", "torchvision": "0.30"}])
def test_partial_or_blank_runtime_declarations_are_refused(pins):
    classifier, proposer = metadata()
    classifier.update(pins)
    with pytest.raises(ValueError, match="runtime"):
        shared_regional_version({"classifier": classifier, "proposer": proposer})


def test_historical_missing_runtime_keeps_its_existing_semantic_hash():
    from weedz.annotation.semantic import classifier_runtime

    classifier, proposer = metadata()
    legacy = {"classifier": classifier, "proposer": proposer}
    assert shared_regional_version(legacy)["sha256"] == (
        "6eec69ef7c79d25862354b2c44687fa300ef42382e540a0aa1d1c31fd37e87c8"
    )
    assert classifier_runtime(legacy) == {
        "status": "historical_unrecorded",
        "pillow": None,
        "torchvision": None,
    }


def test_masked_crop_padding_and_geometry_revision_bind_shared_identity():
    classifier, proposer = metadata()
    legacy = {"classifier": classifier, "proposer": proposer}
    rectangular = dict(legacy, crop_geometry_revision=1)
    padded: dict[str, Any] = dict(
        legacy,
        crop_geometry_revision=2,
        masked_view_policy={
            "padding": "centred square",
            "colour": [124, 116, 104],
            "transform": "recorded timm preprocessing",
        },
    )
    changed = deepcopy(padded)
    changed["masked_view_policy"]["colour"][0] = 125
    versions = [
        shared_regional_version(value)["sha256"] for value in (legacy, rectangular, padded, changed)
    ]
    assert len(set(versions)) == 4
