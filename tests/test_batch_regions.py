"""Actual masked-region misses and explicitly audited legacy adoption remain distinct."""

import json

import numpy as np
from test_batch_compute import Model
from test_batch_proposals import Proposer
from test_closed_batch import batch as batch
from test_closed_batch import reference

from weedz.batches.profiles import ModelProfile
from weedz.batches.proposal_compute import segment
from weedz.batches.regional_compute import regions
from weedz.batches.storage import validate_closed_batch


class Masks(Proposer):
    def generate(self, image):
        self.calls += 1
        return [
            {
                "segmentation": np.ones((image.height, image.width), dtype=bool),
                "predicted_iou": 1.0,
                "stability_score": 1.0,
            }
        ]


def test_masked_miss_computes_and_audited_legacy_adoption_never_recomputes(batch):
    root, manifest, ready, _ = batch
    closed = validate_closed_batch(root, reference(manifest, root), reference(ready, root))
    sam = Masks()
    proposal_profile = ModelProfile("sam2-v1", "proposals", sam.metadata, lambda: sam)
    proposals = segment(root, closed, "outputs/proposals", proposal_profile)
    model = Model()
    model.metadata.update(
        input_policy="Actual SAM masked crop only; source taxonomy not supplied",
        proposer=sam.metadata,
        proposer_kind="sam2",
        primary_view="masked",
        crop_geometry_revision=1,
    )
    loads = []
    profile = ModelProfile(
        "plantclef-regions-v1", "regions", model.metadata, lambda: loads.append(1) or model
    )
    first = regions(
        root, closed, proposals.artifact, "outputs/regions.json", profile, proposal_profile
    )
    assert first.origin == "temporal-activity" and model.calls == 1
    retry = regions(
        root, closed, proposals.artifact, "outputs/regions.json", profile, proposal_profile
    )
    assert retry.origin == "activity-cache" and model.calls == 1 and len(loads) == 1
    legacy = json.loads((root / first.artifact["path"]).read_text())
    legacy.pop("result_sha256")
    legacy.pop("manifest_sha256")
    legacy["model_version"] = "original-external-version"
    for row in legacy["predictions"]:
        row["model_version"] = legacy["model_version"]
    path = root / "legacy.json"
    path.write_text(json.dumps(legacy))
    adopted = regions(
        root,
        closed,
        proposals.artifact,
        "unused.json",
        profile,
        proposal_profile,
        external=reference(path, root),
    )
    assert adopted.origin == "external-compute" and model.calls == 1 and len(loads) == 1
