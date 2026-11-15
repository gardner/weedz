"""Real activity/package interfaces with fake encoding; hardware proofs are separate."""

import json
from copy import deepcopy

import numpy as np
import pytest
from temporalio.testing import ActivityEnvironment
from test_batch_adoption import inputs as batch_inputs
from test_batch_proposals import Proposer
from test_bioclip_batches import score
from test_closed_batch import batch as batch

from weedz.batches.activities import BatchActivities
from weedz.batches.profiles import ModelProfile
from weedz.batches.proposal_compute import segment
from weedz.batches.runtime import registry_from_config
from weedz.batches.storage import validate_closed_batch
from weedz.classification.bioclip import KIND, BioClipClassifier
from weedz.discovery.inference import LABELS, MODELS, RANKING_REVISION, prompt


def model():
    class Screener:
        metadata = {
            "model_key": "bioclip-2",
            "model": MODELS["bioclip-2"]["repo"],
            "revision": MODELS["bioclip-2"]["revision"],
            "weights_sha256": "a" * 64,
            "backend_profile": "cuda-fp32-v1",
            "device": "cuda:0",
            "scoring_device": "cpu",
            "precision": "float32",
            "math_policy": {"cuda_matmul_tf32": False, "cudnn_tf32": False, "autocast": False},
            "ranking_revision": RANKING_REVISION,
            "prompts": [prompt(label) for label in LABELS],
            "embedding_cache": {"preprocessing_sha256": "b" * 64},
            "cuda": "13.2",
            "cudnn": 1,
            "gpu": "test GPU",
            "numpy": "test",
        }

    class TestClassifier(BioClipClassifier):
        calls = 0

    result = TestClassifier(Screener())
    result.calls = 0

    def frame(encoded):
        result.calls += 1
        import io

        from PIL import Image

        with Image.open(io.BytesIO(encoded)) as image:
            return score(*image.size)

    def regions(views):
        result.calls += 1
        return {name: score() for name in views}

    result.frame = frame
    result.regions = regions
    return result


def config(proposer, classifier):
    return {
        "classifier_kind": KIND,
        "device": "cuda:0",
        "classifier_profile": "bioclip-margins-v1",
        "segmentation_profile": "sam2.1-tiny-v1",
        "proposer_kind": "sam2",
        "embedding_cache": "/unused",
        "model_key": "bioclip-2",
        "metadata": {
            "proposals": proposer,
            "frame": classifier.profile_metadata("frame"),
            "regions": classifier.profile_metadata("regions", proposer),
        },
    }


def test_six_activity_pipeline_creates_margin_native_editable_package_and_retries(
    batch, monkeypatch
):
    from weedz.batches.package import validate_package

    root, request = batch_inputs(batch)
    closed = validate_closed_batch(root, request["manifest"], request["ready"])

    class Masks(Proposer):
        def generate(self, image):
            return [
                {
                    "segmentation": np.ones((image.height, image.width), bool),
                    "predicted_iou": 0.9,
                    "stability_score": 0.95,
                }
            ]

    sam = Masks()
    proposals = segment(
        root, closed, "cached", ModelProfile("sam-v1", "proposals", sam.metadata, lambda: sam)
    )
    classifier = model()
    worker = config(sam.metadata, classifier)
    monkeypatch.setattr(BioClipClassifier, "load", lambda *_: classifier)
    registry = registry_from_config(worker)
    request.update(
        segmentation_profile=worker["segmentation_profile"],
        classifier_profile=worker["classifier_profile"],
        variants=["frame", "regions"],
        cached={"proposals": proposals.artifact},
    )
    payload = {"request": request, "completed": {}}
    activities = BatchActivities(root, registry)
    env = ActivityEnvironment()
    names = [
        "batch_validate_v1",
        "batch_segment_v1",
        "batch_classify_frame_v1",
        "batch_classify_regions_v1",
        "batch_package_v1",
    ]
    for name in names:
        payload["completed"][name] = env.run(getattr(activities, name), payload)
    receipt = json.loads((root / payload["completed"]["batch_package_v1"]["path"]).read_text())
    package = validate_package(
        (root / receipt["artifact"]["path"]).parent, receipt["artifact"]["sha256"]
    )
    native = [p for p in package.tasks[0]["predictions"] if "BioCLIP GPU" in p["model_version"]]
    assert len(native) == 2
    assert any(r["type"] == "brushlabels" for p in native for r in p["result"])
    assert "window_similarities" in json.dumps(native)
    assert "softmax" not in json.dumps(native)
    calls = classifier.calls
    for name in names:
        assert env.run(getattr(activities, name), payload) == payload["completed"][name]
    assert classifier.calls == calls
    bad = deepcopy(worker)
    bad["proposer_kind"] = "sam3"
    with pytest.raises(ValueError):
        registry_from_config(bad)
    with pytest.raises(RuntimeError):
        registry.segmentation[worker["segmentation_profile"]].load()


def test_reusable_regional_profile_ignores_corpus_notes_but_binds_sam_policy():
    from test_annotation_versions import metadata

    classifier = model()
    proposer = metadata()[1]
    first = classifier.profile_metadata("regions", proposer)
    annotated = {**proposer, "corpus_note": "different valid source batch"}
    assert classifier.profile_metadata("regions", annotated) == first
    changed = deepcopy(proposer)
    changed["proposal_config"]["context_fraction"] = 0.1
    assert classifier.profile_metadata("regions", changed) != first
