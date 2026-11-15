"""WeedScan is a distinct CPU classifier, including real source-bound regional views."""

import json
from copy import deepcopy

import pytest
from test_annotation_versions import metadata
from test_classification_regions import inputs
from test_closed_batch import batch as batch

from weedz.classification.regions import classify_region_batch, regional_metadata


def weed_metadata():
    from weedz.classification.weedscan import CLASS_COUNT, LABELS_SHA256, RELEASE, WEIGHTS_SHA256

    return {
        "model": "WeedScan MobileNetV2 ORT",
        "pipeline_name": "WeedScan488",
        "release": RELEASE,
        "weights_sha256": WEIGHTS_SHA256,
        "labels_sha256": LABELS_SHA256,
        "class_count": CLASS_COUNT,
        "device": "cpu",
        "precision": "float32",
        "onnxruntime": "1.32.0",
        "numpy": "2.5.4",
        "pillow": "13.0.0",
        "preprocessing": {"resize_short_edge": 480, "crop": [480, 480]},
        "frame_input_policy": "upright canonical RGB, released bicubic480",
        "score_kind": "closed_set_softmax_uncalibrated",
        "supported_profiles": ["frame"],
        "licence": "CC-BY-NC-4.0",
    }


class Model:
    def __init__(self):
        self.metadata = weed_metadata()
        self.calls = 0

    def predict(self, images, top_k=5):
        self.calls += 1
        return [[{"taxon": "Cortaderia", "score": 0.8}] for _ in images]


def config():
    from weedz.classification.batch import classifier_metadata

    model, proposer = Model(), metadata()[1]
    return {
        "classifier_kind": "weedscan-ort-cpu-v1",
        "device": "cpu",
        "proposer_kind": "sam2",
        "segmentation_profile": "sam2.1-tiny-v1",
        "classifier_profile": "weedscan488-v1",
        "classifier_checkpoint": "/unused/model.ort",
        "classifier_labels": "/unused/taxonomy.json",
        "metadata": {
            "proposals": proposer,
            "frame": classifier_metadata(model, "frame"),
            "regions": regional_metadata(model, proposer, "sam2"),
        },
    }


def test_region_classifier_keeps_three_views_and_masked_primary_then_reuses_cache(tmp_path):
    manifest, proposal, original = inputs(tmp_path)
    model = Model()
    output = tmp_path / "weedscan.json"
    result = classify_region_batch(manifest, tmp_path, proposal, output, model, "sam3")
    region = result["predictions"][0]["regions"][0]
    assert set(region["views"]) == {"tight", "masked", "context"}
    assert region["topk"] == region["views"]["masked"]
    assert region["id"] == original["segmentation"]["regions"][0]["id"]
    assert "WeedScan488" in result["model_version"]
    assert "PlantCLEF" not in json.dumps(result)
    assert model.calls == 3
    assert classify_region_batch(manifest, tmp_path, proposal, output, model, "sam3") == result
    assert model.calls == 3


@pytest.mark.parametrize("damage", ["missing_view", "nonfinite_view", "wrong_primary"])
def test_cached_alternative_views_are_validated_even_with_recomputed_digest(tmp_path, damage):
    from weedz.segmentation.artifacts import digest

    manifest, proposal, _ = inputs(tmp_path)
    model, output = Model(), tmp_path / "weedscan.json"
    result = classify_region_batch(manifest, tmp_path, proposal, output, model, "sam3")
    region = result["predictions"][0]["regions"][0]
    if damage == "missing_view":
        del region["views"]["tight"]
    elif damage == "nonfinite_view":
        region["views"]["context"][0]["score"] = 2
    else:
        region["topk"] = [{"taxon": "Different", "score": 0.5}]
    result["result_sha256"] = digest({k: v for k, v in result.items() if k != "result_sha256"})
    output.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="view|score"):
        classify_region_batch(manifest, tmp_path, proposal, output, model, "sam3")
    assert model.calls == 3


def test_empty_sam_keeps_a_valid_empty_region_result_without_identifying_absence(tmp_path):
    manifest, proposal, _ = inputs(tmp_path, empty=True)
    model = Model()
    result = classify_region_batch(manifest, tmp_path, proposal, tmp_path / "out", model, "sam3")
    assert result["predictions"][0]["regions"] == []
    assert model.calls == 0


def test_classifier_cannot_return_an_extra_region_result(tmp_path):
    manifest, proposal, _ = inputs(tmp_path)

    class Extra(Model):
        def predict(self, images, top_k=5):
            return super().predict(images, top_k) + [[{"taxon": "Extra", "score": 0.2}]]

    with pytest.raises(ValueError, match="count"):
        classify_region_batch(manifest, tmp_path, proposal, tmp_path / "out", Extra(), "sam3")


def test_semantic_version_binds_onnx_policy_and_each_region_view():
    from weedz.annotation.semantic import shared_regional_version
    from weedz.batches.weedscan_runtime import weedscan_identity

    model = config()["metadata"]["regions"]
    original = shared_regional_version(model)
    assert "WeedScan488" in original["model_version"]
    assert "torch" not in original["semantic"]["classifier"]
    assert weedscan_identity(model, "regions")
    for field, value in [("onnxruntime", "new"), ("views", ["masked"])]:
        changed = {**model, field: value}
        if field == "views":
            with pytest.raises(ValueError, match="view"):
                weedscan_identity(changed, "regions")
        else:
            assert shared_regional_version(changed)["sha256"] != original["sha256"]


def test_sam3_registry_uses_its_own_cached_proposal_kind(tmp_path):
    from test_batch_sam3 import metadata as sam_metadata
    from test_sam3_batch import Processor

    from weedz.batches.runtime import registry_from_config
    from weedz.segmentation.sam3_image import Sam3Config, Sam3Image

    worker = config()
    sam = Sam3Image(Processor(), Sam3Config(), sam_metadata(), tmp_path / "cache")
    worker["metadata"]["proposals"] = sam.metadata
    worker["metadata"]["regions"] = regional_metadata(Model(), sam.metadata, "sam3")
    worker.update(proposer_kind="sam3", segmentation_profile="sam3-image-concept-v1")
    registry = registry_from_config(worker)
    assert registry.proposer_kinds["sam3-image-concept-v1"] == "sam3"


def test_direct_region_export_has_weedscan_name_without_override():
    from weedz.annotation.auto_labels import regional_prediction

    result = regional_prediction([], config()["metadata"]["regions"], (6, 4))
    assert "WeedScan488" in result["model_version"]
    assert "PlantCLEF" not in json.dumps(result)


def test_registry_never_runs_sam_and_refuses_wrong_proposer_or_cpu_identity():
    from weedz.batches.runtime import registry_from_config

    worker = config()
    registry = registry_from_config(worker)
    request = {
        "segmentation_profile": worker["segmentation_profile"],
        "classifier_profile": worker["classifier_profile"],
        "variants": ["frame", "regions"],
        "cached": {},
    }
    with pytest.raises(ValueError, match="cached proposal"):
        registry.pins(request)
    request["cached"]["proposals"] = {"path": "proposals.jsonl", "sha256": "a" * 64}
    assert set(registry.pins(request)) == {"proposals", "frame", "regions"}
    with pytest.raises(RuntimeError, match="never run"):
        registry.segmentation[worker["segmentation_profile"]].load()
    for field, value in [("device", "cuda:0"), ("proposer_kind", "sam3"), ("cache_only", True)]:
        with pytest.raises(ValueError):
            registry_from_config({**worker, field: value})
    changed = deepcopy(worker)
    changed["metadata"]["frame"]["weights_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        registry_from_config(changed)


def test_frame_export_preserves_genus_and_actual_cpu_runtime():
    from weedz.annotation.auto_labels import frame_prediction

    result = frame_prediction(
        [{"taxon": "Cortaderia", "score": 0.8}], config()["metadata"]["frame"]
    )
    assert result["model_version"].startswith("WeedScan488 frame")
    assert result["result"][0]["value"]["text"] == ["Cortaderia"]
    text = json.dumps(result)
    assert "onnxruntime" in text and "CC-BY-NC-4.0" in text
    assert "PlantCLEF" not in text and "torchvision" not in text
    assert "uncalibrated" in text


def test_three_view_activity_package_and_retry_do_not_rerun_models(batch, monkeypatch):
    import numpy as np
    from temporalio.testing import ActivityEnvironment
    from test_batch_adoption import inputs as batch_inputs
    from test_batch_proposals import Proposer

    from weedz.batches.activities import BatchActivities
    from weedz.batches.package import validate_package
    from weedz.batches.profiles import ModelProfile
    from weedz.batches.proposal_compute import segment
    from weedz.batches.runtime import registry_from_config
    from weedz.batches.storage import validate_closed_batch
    from weedz.classification.weedscan import WeedScanClassifier

    root, request = batch_inputs(batch)
    closed = validate_closed_batch(root, request["manifest"], request["ready"])

    class Masked(Proposer):
        def generate(self, image):
            return [
                {
                    "segmentation": np.ones((image.height, image.width), bool),
                    "predicted_iou": 0.9,
                    "stability_score": 0.95,
                }
            ]

    sam = Masked()
    proposals = segment(
        root, closed, "masked", ModelProfile("sam-v1", "proposals", sam.metadata, lambda: sam)
    )
    model = Model()
    monkeypatch.setattr(WeedScanClassifier, "load", lambda *_: model)
    worker = config()
    worker["metadata"]["proposals"] = sam.metadata
    worker["metadata"]["regions"] = regional_metadata(model, sam.metadata, "sam2")
    registry = registry_from_config(worker)
    request.update(
        segmentation_profile=worker["segmentation_profile"],
        classifier_profile=worker["classifier_profile"],
        variants=["frame", "regions"],
        cached={"proposals": proposals.artifact},
    )
    activities = BatchActivities(root, registry)
    payload = {"request": request, "completed": {}}
    env = ActivityEnvironment()
    methods = (
        activities.batch_validate_v1,
        activities.batch_segment_v1,
        activities.batch_classify_frame_v1,
        activities.batch_classify_regions_v1,
        activities.batch_package_v1,
    )
    for method in methods:
        payload["completed"][method.__name__] = env.run(method, payload)
    receipt = json.loads((root / payload["completed"]["batch_package_v1"]["path"]).read_text())
    package = validate_package(
        (root / receipt["artifact"]["path"]).parent, receipt["artifact"]["sha256"]
    )
    predictions = package.tasks[0]["predictions"]
    assert len([p for p in predictions if "WeedScan488" in p["model_version"]]) == 2
    regional = next(p for p in predictions if "WeedScan488 masked" in p["model_version"])
    assert any(r["type"] == "brushlabels" for r in regional["result"])
    assert "tight" in json.dumps(regional) and "context" in json.dumps(regional)
    assert model.calls == 4
    for method in methods:
        env.run(method, payload)
    assert model.calls == 4
