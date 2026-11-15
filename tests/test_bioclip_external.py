"""External margin artifact references remain immutable across adoption races."""

import json

import pytest
from test_batch_adoption import inputs as batch_inputs
from test_bioclip_workflow import model
from test_closed_batch import batch as batch

from weedz.batches.bioclip_compute import run
from weedz.batches.profiles import ModelProfile
from weedz.batches.storage import validate_closed_batch
from weedz.classification.bioclip import identity
from weedz.segmentation.artifacts import digest


@pytest.mark.parametrize("hookpoint", ["before_runner", "after_runner"])
@pytest.mark.parametrize("external", [True, False])
def test_external_replacement_cannot_change_the_requested_reference(
    batch, monkeypatch, hookpoint, external
):
    from weedz.batches import bioclip_compute

    root, request = batch_inputs(batch)
    closed = validate_closed_batch(root, request["manifest"], request["ready"])
    classifier = model()
    from weedz.batches.bioclip_runtime import View

    profile = ModelProfile(
        "margin-v1",
        "frame",
        classifier.profile_metadata("frame"),
        lambda: View(classifier, "frame", None),
        identity=identity,
    )
    original = run(root, closed, "frame.json", profile)
    path = root / original.artifact["path"]
    encoded = path.read_bytes()
    target = "_model" if hookpoint == "before_runner" else "classify_margin_batch"
    real_action = getattr(bioclip_compute, target)

    def replace_after_verified(*args, **kwargs):
        result = real_action(*args, **kwargs)
        changed = json.loads(encoded)
        changed["unrequested_note"] = "replacement"
        changed["result_sha256"] = digest(
            {k: v for k, v in changed.items() if k != "result_sha256"}
        )
        path.write_text(json.dumps(changed))
        return result

    monkeypatch.setattr(bioclip_compute, target, replace_after_verified)
    relative = "unused.json" if external else "frame.json"
    pinned = original.artifact if external else None
    with pytest.raises(ValueError, match="checksum"):
        run(root, closed, relative, profile, external=pinned)
    path.write_bytes(encoded)
    monkeypatch.setattr(bioclip_compute, target, real_action)
    calls = classifier.calls
    assert run(root, closed, relative, profile, external=pinned).artifact == original.artifact
    assert classifier.calls == calls
