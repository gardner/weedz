"""Formal writers reject replacement inputs before poisoning immutable activity outputs."""

import pytest
from test_batch_compute import Model
from test_batch_regions import Masks
from test_closed_batch import batch as batch
from test_closed_batch import reference

from weedz.batches.profiles import ModelProfile
from weedz.batches.proposal_compute import segment
from weedz.batches.storage import validate_closed_batch
from weedz.classification.regions import regional_metadata


@pytest.mark.parametrize("kind", ["frame", "tiles"])
def test_manifest_replacement_before_writer_cannot_poison_retry(batch, monkeypatch, kind):
    import weedz.batches.compute as module

    root, manifest, ready, _ = batch
    closed = validate_closed_batch(root, reference(manifest, root), reference(ready, root))
    original_bytes = manifest.read_bytes()
    model = Model()
    from weedz.classification.batch import classifier_metadata

    model.metadata = classifier_metadata(model, kind)
    profile = ModelProfile("classifier-v1", kind, model.metadata, lambda: model)
    original_writer = module.classify_batch

    def replace_then_write(*args, **kwargs):
        manifest.write_bytes(b" " + original_bytes)
        return original_writer(*args, **kwargs)

    monkeypatch.setattr(module, "classify_batch", replace_then_write)
    with pytest.raises(ValueError):
        module.classify(root, closed, "results/frame.json", profile)
    assert model.calls == 0
    assert not (root / "results/frame.json").exists()
    manifest.write_bytes(original_bytes)
    monkeypatch.setattr(module, "classify_batch", original_writer)
    assert (
        module.classify(root, closed, "results/frame.json", profile).origin == "temporal-activity"
    )
    assert model.calls == 1


@pytest.mark.parametrize("replacement", ["manifest", "proposals"])
def test_proposal_replacement_before_regional_writer_cannot_poison_retry(
    batch, monkeypatch, replacement
):
    import weedz.batches.regional_compute as module

    root, manifest, ready, _ = batch
    closed = validate_closed_batch(root, reference(manifest, root), reference(ready, root))
    sam = Masks()
    proposer = ModelProfile("sam-v1", "proposals", sam.metadata, lambda: sam)
    proposals = segment(root, closed, "results/proposals", proposer).artifact
    path = root / proposals["path"]
    original_bytes = path.read_bytes()
    original_manifest = manifest.read_bytes()
    model = Model()
    model.metadata = regional_metadata(model, sam.metadata, "sam2")
    profile = ModelProfile("regions-v1", "regions", model.metadata, lambda: model)
    original_writer = module.classify_region_batch

    def replace_then_write(*args, **kwargs):
        if replacement == "proposals":
            path.write_bytes(b" " + original_bytes)
        else:
            manifest.write_bytes(b" " + original_manifest)
        return original_writer(*args, **kwargs)

    monkeypatch.setattr(module, "classify_region_batch", replace_then_write)
    with pytest.raises(ValueError):
        module.regions(root, closed, proposals, "results/regions.json", profile, proposer)
    assert model.calls == 0
    assert not (root / "results/regions.json").exists()
    path.write_bytes(original_bytes)
    manifest.write_bytes(original_manifest)
    monkeypatch.setattr(module, "classify_region_batch", original_writer)
    assert (
        module.regions(root, closed, proposals, "results/regions.json", profile, proposer).origin
        == "temporal-activity"
    )
    assert model.calls == 1
