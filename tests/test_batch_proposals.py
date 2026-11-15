"""Proposal cache misses execute the injected model; complete artifacts are validated and reused."""

from test_annotation_versions import metadata
from test_closed_batch import batch as batch
from test_closed_batch import reference

from weedz.batches.profiles import ModelProfile
from weedz.batches.proposal_compute import segment
from weedz.batches.storage import validate_closed_batch


class Proposer:
    def __init__(self):
        self.metadata = metadata()[1]
        self.calls = 0

    def generate(self, image):
        self.calls += 1
        return []


def test_real_miss_and_verified_empty_result_cache_do_not_invent_absence_labels(batch):
    root, manifest, ready, _ = batch
    closed = validate_closed_batch(root, reference(manifest, root), reference(ready, root))
    model = Proposer()
    loads = []
    profile = ModelProfile(
        "sam2.1-v1", "proposals", model.metadata, lambda: loads.append(1) or model
    )
    first = segment(root, closed, "results/proposals", profile)
    assert first.origin == "temporal-activity" and model.calls == 1
    retry = segment(root, closed, "results/proposals", profile)
    assert retry.origin == "activity-cache" and retry.artifact == first.artifact
    adopted = segment(root, closed, "unused", profile, external=first.artifact)
    assert adopted.origin == "external-compute" and adopted.artifact == first.artifact
    assert model.calls == 1 and len(loads) == 1
    assert not (root / "unused").exists()
