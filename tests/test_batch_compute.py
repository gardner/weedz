"""A cache miss computes, while verified external adoption never loads or runs a model."""

from test_annotation_versions import metadata
from test_closed_batch import batch as batch
from test_closed_batch import reference

from weedz.batches.compute import classify
from weedz.batches.profiles import ModelProfile
from weedz.batches.storage import validate_closed_batch


class Model:
    def __init__(self):
        self.metadata = {
            **metadata()[0],
            "input_policy": (
                "EXIF-upright source pixels; timm resize and centre crop; "
                "no source taxonomy supplied"
            ),
        }
        self.calls = 0

    def predict(self, images, top_k=5):
        self.calls += 1
        return [[{"taxon": "Ulex europaeus", "score": 0.4}] for _ in images]


def test_miss_computes_once_then_retry_and_explicit_adoption_do_not_load_models(batch):
    root, manifest, ready, _ = batch
    closed = validate_closed_batch(root, reference(manifest, root), reference(ready, root))
    model = Model()
    loads = []
    profile = ModelProfile(
        "plantclef-frame-v1", "frame", model.metadata, lambda: loads.append(1) or model
    )
    first = classify(root, closed, "results/frame.json", profile)
    assert first.origin == "temporal-activity"
    assert model.calls == 1 and len(loads) == 1
    retry = classify(root, closed, "results/frame.json", profile)
    assert retry.origin == "activity-cache" and retry.artifact == first.artifact
    adopted = classify(root, closed, "unused/frame.json", profile, external=first.artifact)
    assert adopted.origin == "external-compute" and adopted.artifact == first.artifact
    assert model.calls == 1 and len(loads) == 1
    assert not (root / "unused").exists()
