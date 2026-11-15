"""Legacy preparation verifies closed evidence and makes cache misses fail closed."""

import pytest
from test_batch_compute import Model
from test_batch_proposals import Proposer
from test_closed_batch import batch as batch
from test_closed_batch import reference

from weedz.batches.compute import classify
from weedz.batches.profiles import ModelProfile
from weedz.batches.proposal_compute import segment
from weedz.batches.storage import validate_closed_batch


def inputs(batch):
    root, manifest, ready, _ = batch
    closed = validate_closed_batch(root, reference(manifest, root), reference(ready, root))
    sam, model = Proposer(), Model()
    proposals = segment(
        root,
        closed,
        "legacy/proposals",
        ModelProfile("sam-v1", "proposals", sam.metadata, lambda: sam),
    )
    frame = classify(
        root,
        closed,
        "legacy/frame.json",
        ModelProfile("classifier-v1", "frame", model.metadata, lambda: model),
    )
    return root, {
        "manifest": reference(manifest, root),
        "ready": reference(ready, root),
        "segmentation_profile": "sam-legacy-v1",
        "classifier_profile": "classifier-legacy-v1",
        "variants": ["frame"],
        "project_id": 1,
        "cached": {"proposals": proposals.artifact, "frame": frame.artifact},
    }


def test_adoption_configuration_keeps_original_metadata_and_forbids_inference(batch):
    from weedz.batches.adoption import prepare_adoption
    from weedz.batches.runtime import registry_from_config

    root, request = inputs(batch)
    config = prepare_adoption(root, request)
    assert config["cache_only"] is True
    registry = registry_from_config(config)
    assert registry.pins(request)
    with pytest.raises(RuntimeError, match="cache-only"):
        registry.classifiers[request["classifier_profile"]]["frame"].load()
    assert config["metadata"]["frame"] == Model().metadata


def test_adoption_rejects_missing_cache_or_replaced_closed_evidence(batch):
    from weedz.batches.adoption import prepare_adoption

    root, request = inputs(batch)
    missing = {**request, "cached": {"proposals": request["cached"]["proposals"]}}
    with pytest.raises(ValueError, match="every requested"):
        prepare_adoption(root, missing)
    (root / request["cached"]["frame"]["path"]).write_bytes(b"replaced")
    with pytest.raises(ValueError, match="checksum"):
        prepare_adoption(root, request)


def test_regional_adoption_validates_proposal_join_without_rewriting(batch):
    import json

    from weedz.batches.adoption import prepare_adoption
    from weedz.batches.regional_compute import regions
    from weedz.classification.regions import regional_metadata

    root, request = inputs(batch)
    closed = validate_closed_batch(root, request["manifest"], request["ready"])
    sam = Proposer()
    model = Model()
    model.metadata = regional_metadata(model, sam.metadata, "sam2")
    result = regions(
        root,
        closed,
        request["cached"]["proposals"],
        "legacy/regions.json",
        ModelProfile("classifier-regions-v1", "regions", model.metadata, lambda: model),
        ModelProfile("sam-v1", "proposals", sam.metadata, lambda: sam),
    )
    request["variants"].append("regions")
    request["cached"]["regions"] = result.artifact
    original = (root / result.artifact["path"]).read_bytes()
    assert prepare_adoption(root, request)["metadata"]["regions"] == model.metadata
    assert (root / result.artifact["path"]).read_bytes() == original
    document = json.loads(original)
    document["proposals_sha256"] = "0" * 64
    path = root / "wrong-regions.json"
    path.write_text(json.dumps(document))
    request["cached"]["regions"] = reference(path, root)
    with pytest.raises(ValueError, match="source provenance"):
        prepare_adoption(root, request)


def test_maximum_length_registered_classifier_profile_can_be_adopted(batch):
    from weedz.batches.adoption import prepare_adoption
    from weedz.batches.contract import batch_request
    from weedz.batches.runtime import registry_from_config

    root, request = inputs(batch)
    request["classifier_profile"] = "c" * 80
    assert batch_request(request)["classifier_profile"] == request["classifier_profile"]
    config = prepare_adoption(root, request)
    registry = registry_from_config(config)
    assert (
        registry.classifiers[request["classifier_profile"]]["frame"].name
        == request["classifier_profile"]
    )


def test_maximum_length_profile_can_register_all_resident_classifier_kinds():
    from weedz.batches.runtime import registry_from_config
    from weedz.classification.batch import classifier_metadata
    from weedz.classification.regions import regional_metadata

    model, sam = Model(), Proposer()
    name = "c" * 80
    config = {
        "device": "cpu",
        "segmentation_profile": "sam-v1",
        "classifier_profile": name,
        "metadata": {
            "proposals": sam.metadata,
            "frame": classifier_metadata(model, "frame"),
            "tiles": classifier_metadata(model, "tiles"),
            "regions": regional_metadata(model, sam.metadata, "sam2"),
        },
    }
    registry = registry_from_config(config)
    assert {profile.name for profile in registry.classifiers[name].values()} == {name}
    assert {profile.kind for profile in registry.classifiers[name].values()} == {
        "frame",
        "tiles",
        "regions",
    }
