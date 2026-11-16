"""CLI ingress cannot relabel a checksum-bound proposal profile."""

import hashlib
import json
from dataclasses import asdict

import pytest
from region_helpers import sample
from test_annotation_versions import metadata

from weedz.manifest import write_manifest
from weedz.region_evaluation.cli import _inputs, parser
from weedz.segmentation.ingress import proposal_metadata
from weedz.segmentation.sam3_image import Sam3Config


def arguments(root, stored, requested, kind):
    record = sample()
    manifest = root / "samples.jsonl"
    write_manifest(manifest, [record])
    profile = metadata()[1]
    if kind == "sam3":
        profile.update(
            profile="sam3-image-concept-v1",
            checkpoint_revision="weights",
            processor_resolution=1008,
            processor_output_threshold=0.0,
            mask_probability_threshold=0.5,
            score_kind="uncalibrated_concept_score",
            calibrated=False,
            precision="FP32 weights; BF16 CUDA autocast",
            config=asdict(Sam3Config()),
        )
    profile = proposal_metadata(profile, stored)
    row = {
        "sample_id": record.id,
        "image_sha256": record.media.sha256,
        "model_version": "test-profile",
        "segmentation": {"status": "empty", "regions": [], "provenance": profile},
    }
    encoded = (json.dumps(row) + "\n").encode()
    (root / "proposals.jsonl").write_bytes(encoded)
    ready = root / "ready.json"
    ready.write_text(
        json.dumps(
            {
                "schema": 1,
                "count": 1,
                "model_version": "test-profile",
                "manifest_sha256": "b" * 64,
                "proposals_sha256": hashlib.sha256(encoded).hexdigest(),
            }
        )
    )

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    args = [
        "--mode",
        "boxes",
        "--manifest",
        str(manifest),
        "--manifest-sha256",
        sha(manifest),
        "--assets-root",
        str(root),
        "--proposals-ready",
        str(ready),
        "--ready-sha256",
        sha(ready),
        "--proposer",
        kind,
        "--output",
        str(root / "output"),
    ]
    if requested is not None:
        args.extend(["--max-source-bytes", str(requested)])
    return parser().parse_args(args)


@pytest.mark.parametrize("kind", ["sam2", "sam3"])
@pytest.mark.parametrize(
    "stored,requested",
    [
        (None, 160_000_000),
        (160_000_000, None),
        (80_000_000, 160_000_000),
        (20_000_000, None),
        (None, 20_000_000),
    ],
)
def test_cli_refuses_ingress_identity_mismatch_before_decoding(tmp_path, kind, stored, requested):
    args = arguments(tmp_path, stored, requested, kind)
    with pytest.raises(ValueError, match="ingress"):
        _inputs(args)
    assert not args.output.exists()


@pytest.mark.parametrize("kind", ["sam2", "sam3"])
@pytest.mark.parametrize("budget", [None, 20_000_000, 160_000_000])
def test_matching_explicit_and_historical_default_ingress_remain_usable(tmp_path, kind, budget):
    args = arguments(tmp_path, budget, budget, kind)
    samples, proposed, classifier, taxonomy = _inputs(args)
    assert len(samples) == len(proposed.rows) == 1
    assert classifier is taxonomy is None
