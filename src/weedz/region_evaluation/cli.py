"""Private, source-labelled region diagnostics; this command never invokes inference."""

import argparse
import hashlib
from pathlib import Path

from weedz.batches.receipts import write_receipt
from weedz.manifest import read_manifest
from weedz.region_evaluation.proposal_inputs import load_proposals
from weedz.region_evaluation.semantic import sparse_report
from weedz.segmentation.ingress import proposal_metadata


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--manifest", required=True, type=Path)
    command.add_argument("--manifest-sha256", required=True)
    command.add_argument("--assets-root", required=True, type=Path)
    command.add_argument("--proposals-ready", required=True, type=Path)
    command.add_argument("--ready-sha256", required=True)
    command.add_argument("--proposer", required=True, choices=("sam2", "sam3"))
    command.add_argument("--max-source-bytes", type=int, default=None)
    command.add_argument(
        "--output", required=True, type=Path, help="Existing private artifact directory outside Git"
    )
    return command


def main() -> None:
    args = parser().parse_args()
    samples = read_manifest(args.manifest, args.manifest_sha256)
    batch = load_proposals(args.proposals_ready, args.ready_sha256, samples)
    cases = sparse_report(
        samples, args.assets_root, batch, kind=args.proposer, max_source_bytes=args.max_source_bytes
    )
    references = []
    for case in cases:
        key = hashlib.sha256(case["sample_id"].encode("utf-8")).hexdigest()
        references.append(write_receipt(args.output, f"cases/{key}.json", case))
    reference = write_receipt(
        args.output,
        "report.json",
        {
            "schema": 1,
            "metric": "source-labelled positive pixel coverage",
            "label_manifest_sha256": args.manifest_sha256,
            "inference_manifest_sha256": batch.manifest_sha256,
            "ready_sha256": batch.ready_sha256,
            "proposals_sha256": batch.proposals_sha256,
            "model_version": batch.model_version,
            "proposal_budgets": [1, 10, 100],
            "sample_count": len(cases),
            "cases": references,
            "interpretation": (
                "Sparse labelled support only; no full-scene/instance/species accuracy"
            ),
            "human_review": "Source origin retained; no independent NZ review or gold promotion",
            **proposal_metadata({}, args.max_source_bytes),
        },
    )
    print(reference["sha256"])


if __name__ == "__main__":
    main()
