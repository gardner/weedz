"""Inference profiles bind algorithm pins without treating GPU numbering as a new model."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from test_annotation_versions import metadata

from weedz.batches.profiles import ModelProfile


def test_profile_inspection_does_not_start_models_and_device_changes_preserve_identity():
    classifier, _ = metadata()
    classifier["input_policy"] = "Pinned centre crop"
    calls = []
    actual = {**classifier, "device": "cuda:0"}
    profile = ModelProfile(
        "plantclef-frame-v1",
        "frame",
        {**classifier, "device": "cuda:1"},
        lambda: calls.append("load") or SimpleNamespace(metadata=actual),
    )
    assert profile.sha256 and not calls
    assert profile.load().metadata["device"] == "cuda:0"
    assert calls == ["load"]


def test_changed_loaded_weights_cannot_run_as_the_registered_profile():
    classifier, _ = metadata()
    classifier["input_policy"] = "Pinned centre crop"
    changed = {**classifier, "weights_sha256": "f" * 64}
    profile = ModelProfile(
        "plantclef-frame-v1", "frame", classifier, lambda: SimpleNamespace(metadata=changed)
    )
    with pytest.raises(ValueError, match="profile"):
        profile.load()


def test_mask_grid_and_preprocessing_changes_produce_different_pins():
    classifier, proposer = metadata()
    original = ModelProfile("sam2-v1", "proposals", proposer, lambda: None)
    dense = deepcopy(proposer)
    dense["proposal_config"]["points_per_side"] = 32
    assert original.sha256 != ModelProfile("sam2-v1", "proposals", dense, lambda: None).sha256
    classifier["input_policy"] = "Pinned centre crop"
    changed = deepcopy(classifier)
    changed["preprocessing"]["mean"][0] = 0.9
    assert (
        ModelProfile("frame-v1", "frame", classifier, lambda: None).sha256
        != ModelProfile("frame-v1", "frame", changed, lambda: None).sha256
    )


def test_declared_transform_libraries_and_tile_geometry_are_not_legacy_equivalents():
    classifier, _ = metadata()
    classifier.update(input_policy="Pinned tiles", aggregation="max", ranking_revision=1)
    legacy = ModelProfile("tiles-v1", "tiles", classifier, lambda: None)
    recorded = {
        **classifier,
        "pillow": "13",
        "torchvision": "0.29",
        "tile_geometry": {"max_tiles": 32},
    }
    current = ModelProfile("tiles-v2", "tiles", recorded, lambda: None)
    changed = {**recorded, "tile_geometry": {"max_tiles": 64}}
    assert legacy.sha256 != current.sha256
    assert current.sha256 != ModelProfile("tiles-v3", "tiles", changed, lambda: None).sha256


def test_recorded_numpy_and_math_policy_change_the_classifier_identity():
    classifier, _ = metadata()
    classifier["input_policy"] = "Pinned centre crop"
    legacy = ModelProfile("frame-v1", "frame", classifier, lambda: None)
    policy = {"cuda_matmul_tf32": False, "cudnn_tf32": False, "autocast": False}
    recorded = {**classifier, "numpy": "1.26.4", "math_policy": policy}
    current = ModelProfile("frame-v2", "frame", recorded, lambda: None)
    assert current.sha256 != legacy.sha256
    for changed in (
        {**recorded, "numpy": "2.5.4"},
        {**recorded, "math_policy": {**policy, "cuda_matmul_tf32": True}},
    ):
        assert not current.matches(changed)
    with pytest.raises(ValueError, match="math policy"):
        ModelProfile(
            "frame-v2", "frame", {**recorded, "math_policy": {"autocast": False}}, lambda: None
        )
