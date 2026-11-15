"""The NZ Temporal variant has its own all-taxa identity and never runs SAM."""

import json

import pytest
from test_annotation_versions import metadata
from test_closed_batch import batch as batch

from weedz.batches.aotearoa_runtime import aotearoa_identity, registry_from_aotearoa_config
from weedz.classification.aotearoa import CLASS_COUNT, LABELS_SHA256, RELEASE, WEIGHTS_SHA256


def nz_metadata():
    return {
        "model": "Aotearoa Species Classifier EfficientNetV2 small ONNX",
        "pipeline_name": "Aotearoa NZ",
        "release": RELEASE,
        "revision": "pinned",
        "weights_sha256": WEIGHTS_SHA256,
        "labels_sha256": LABELS_SHA256,
        "class_count": CLASS_COUNT,
        "precision": "float32",
        "device": "cpu",
        "onnxruntime": "1.32.0",
        "numpy": "2.5.4",
        "pillow": "13.0.0",
        "preprocessing": {"resize_short_edge": 416, "crop": [384, 384]},
        "input_policy": "released416/384",
        "score_kind": "closed_set_softmax_uncalibrated",
        "supported_profiles": ["frame"],
    }


def config():
    return {
        "classifier_kind": "aotearoa-onnx-cpu-v1",
        "proposer_kind": "sam2",
        "metadata": {"frame": nz_metadata(), "proposals": metadata()[1]},
        "segmentation_profile": "sam2.1-tiny-v1",
        "classifier_profile": "aotearoa-nz-frame-v1",
        "classifier_checkpoint": "/unused/model.onnx",
        "classifier_labels": "/unused/classes.json",
    }


def test_onnx_identity_binds_runtime_normalization_and_all_taxa_without_torch():
    from weedz.batches.profiles import ModelProfile

    model = nz_metadata()
    profile = ModelProfile(
        "aotearoa-nz-frame-v1", "frame", model, lambda: None, identity=aotearoa_identity
    )
    for field, changed in [
        ("onnxruntime", "changed"),
        ("numpy", "changed"),
        ("preprocessing", {"crop": [1, 1]}),
    ]:
        assert not profile.matches({**model, field: changed})
    for invalid in ({**model, "device": "cuda:0"}, {**model, "labels_sha256": "0" * 64}):
        with pytest.raises(ValueError):
            aotearoa_identity(invalid, "frame")
    with pytest.raises(ValueError, match="frame"):
        aotearoa_identity(model, "regions")


def test_registry_requires_external_proposals_and_only_frame():
    registry = registry_from_aotearoa_config(config())
    request = {
        "segmentation_profile": "sam2.1-tiny-v1",
        "classifier_profile": "aotearoa-nz-frame-v1",
        "variants": ["frame"],
        "cached": {},
    }
    with pytest.raises(ValueError, match="cached proposal"):
        registry.pins(request)
    request["cached"]["proposals"] = {"path": "proposals.jsonl", "sha256": "a" * 64}
    assert set(registry.pins(request)) == {"proposals", "frame"}
    with pytest.raises(RuntimeError, match="never run"):
        registry.segmentation["sam2.1-tiny-v1"].load()
    request["variants"] = ["regions"]
    with pytest.raises(ValueError, match="frame"):
        registry.pins(request)


def test_unknown_classifier_kind_cannot_fall_through_to_plantclef():
    from weedz.batches.runtime import registry_from_config

    with pytest.raises(ValueError, match="classifier kind"):
        registry_from_config({"classifier_kind": "unknown"})


def test_all_taxa_export_never_calls_animal_other_plant_or_adds_brushes():
    from weedz.annotation.auto_labels import frame_prediction

    rows = [
        {"taxon": "Chlidonias albostriatus", "score": 0.8},
        {"taxon": "Amanita muscaria", "score": 0.1},
    ]
    result = frame_prediction(rows, nz_metadata())
    assert result["model_version"].startswith("Aotearoa NZ frame verification v1")
    assert result["result"][0]["value"]["text"] == ["Chlidonias albostriatus"]
    assert all(row["type"] != "brushlabels" for row in result["result"])
    text = json.dumps(result)
    assert "Other plant" not in text and "PlantCLEF" not in text
    assert "uncalibrated" in text and "Amanita muscaria" in text


def test_frame_activity_uses_real_registry_then_exports_all_taxa_without_sam_load(
    batch, monkeypatch
):
    from temporalio.testing import ActivityEnvironment
    from test_batch_adoption import inputs

    from weedz.batches.activities import BatchActivities
    from weedz.batches.package import validate_package
    from weedz.batches.runtime import registry_from_config
    from weedz.classification.aotearoa import AotearoaClassifier
    from weedz.classification.batch import classifier_metadata

    root, previous = inputs(batch)

    class Model:
        metadata = {**nz_metadata(), "frame_input_policy": "released416/384"}
        calls = 0

        def predict(self, images, top_k=5):
            self.calls += 1
            return [[{"taxon": "Chlidonias albostriatus", "score": 0.8}] for _ in images]

    model = Model()
    monkeypatch.setattr(AotearoaClassifier, "load", lambda *_args: model)
    worker = config()
    worker["metadata"]["frame"] = classifier_metadata(model, "frame")
    activities = BatchActivities(root, registry_from_config(worker))
    request = {
        **previous,
        "segmentation_profile": worker["segmentation_profile"],
        "classifier_profile": worker["classifier_profile"],
        "cached": {"proposals": previous["cached"]["proposals"]},
    }
    payload = {"request": request, "completed": {}}
    env = ActivityEnvironment()
    for method in (
        activities.batch_validate_v1,
        activities.batch_segment_v1,
        activities.batch_classify_frame_v1,
        activities.batch_package_v1,
    ):
        payload["completed"][method.__name__] = env.run(method, payload)
    receipt = json.loads((root / payload["completed"]["batch_package_v1"]["path"]).read_text())
    package = validate_package(
        (root / receipt["artifact"]["path"]).parent, receipt["artifact"]["sha256"]
    )
    predictions = package.tasks[0]["predictions"]
    frame = next(p for p in predictions if p["model_version"].startswith("Aotearoa NZ"))
    assert frame["result"][0]["value"]["text"] == ["Chlidonias albostriatus"]
    assert "Other plant" not in json.dumps(frame)
    assert not any(r["type"] == "brushlabels" for r in frame["result"])
    env.run(activities.batch_classify_frame_v1, payload)
    assert model.calls == 1


def test_a_cache_only_flag_cannot_accidentally_enable_nz_inference():
    from weedz.batches.runtime import registry_from_config

    with pytest.raises(ValueError, match="cache-only"):
        registry_from_config({**config(), "cache_only": True})


@pytest.mark.parametrize("mismatch", ["kind", "profile"])
def test_runtime_configuration_cannot_restore_another_proposer_as_sam2(mismatch):
    worker = config()
    if mismatch == "kind":
        worker["proposer_kind"] = "sam3"
    else:
        worker["metadata"]["proposals"]["profile"] = "sam3-image-concept-v1"
    with pytest.raises(ValueError, match="cached SAM2"):
        registry_from_aotearoa_config(worker)
