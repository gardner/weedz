"""The same Temporal boundaries execute resident SAM3 and name its model evidence honestly."""

import json

import pytest
from temporalio.testing import ActivityEnvironment
from test_batch_compute import Model
from test_closed_batch import batch as batch
from test_closed_batch import reference
from test_sam3_batch import Processor

from weedz.batches.activities import BatchActivities, BatchRegistry
from weedz.batches.profiles import ModelProfile
from weedz.classification.regions import regional_metadata
from weedz.segmentation.sam3_image import Sam3Config, Sam3Image


def metadata():
    return {
        "model": "SAM3 still-image concept segmentation",
        "code_revision": "sam3-code",
        "checkpoint_revision": "weights-revision",
        "checkpoint_sha256": "d" * 64,
        "processor_resolution": 1008,
        "processor_output_threshold": 0.0,
        "mask_probability_threshold": 0.5,
        "score_kind": "uncalibrated_concept_score",
        "calibrated": False,
        "precision": "FP32 weights; BF16 autocast",
        "torch": "2.10",
        "numpy": "2",
        "pillow": "13",
    }


def test_sam3_prompt_retry_flows_through_classifier_and_current_credit_package(batch):
    root, manifest, ready, _ = batch
    processor = Processor()
    model = Sam3Image(processor, Sam3Config(), metadata(), root / "model-cache")
    classifier = Model()
    regional = Model()
    regional.metadata = regional_metadata(regional, model.metadata, "sam3")
    registry = BatchRegistry(
        {"sam3-v1": ModelProfile("sam3-v1", "proposals", model.metadata, lambda: model)},
        {
            "plantclef-v1": {
                "frame": ModelProfile("frame-v1", "frame", classifier.metadata, lambda: classifier),
                "regions": ModelProfile(
                    "regions-v1", "regions", regional.metadata, lambda: regional
                ),
            }
        },
        {"sam3-v1": "sam3"},
    )
    activities = BatchActivities(root, registry)
    payload = {
        "request": {
            "manifest": reference(manifest, root),
            "ready": reference(ready, root),
            "segmentation_profile": "sam3-v1",
            "classifier_profile": "plantclef-v1",
            "variants": ["frame", "regions"],
            "project_id": 1,
        },
        "completed": {},
    }
    environment = ActivityEnvironment()
    payload["completed"]["batch_validate_v1"] = environment.run(
        activities.batch_validate_v1, payload
    )
    with pytest.raises(RuntimeError, match="failed"):
        environment.run(activities.batch_segment_v1, payload)
    for method in [
        activities.batch_segment_v1,
        activities.batch_classify_frame_v1,
        activities.batch_classify_regions_v1,
        activities.batch_package_v1,
    ]:
        payload["completed"][method.__name__] = environment.run(method, payload)
    receipt = json.loads((root / payload["completed"]["batch_package_v1"]["path"]).read_text())
    package = root / receipt["artifact"]["path"]
    task = json.loads((package.parent / "tasks.json").read_text())[0]
    assert task["data"]["photo_credit"].startswith("Photo: Source author")
    names = [p["model_version"] for p in task["predictions"]]
    assert any(name.startswith("SAM3 + PlantCLEF") for name in names)
    assert any(name.startswith("SAM3 concept region proposals") for name in names)
    assert not any("SAM2" in name for name in names)
    assert processor.calls == ["plant", "flower", "flower"]
