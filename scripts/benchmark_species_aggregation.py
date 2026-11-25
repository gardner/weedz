"""Replay cached ImageWeeds rankings; no inference, training or external writes."""

import argparse
import hashlib
import time
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from weedz.batches.receipts import write_receipt
from weedz.contract import Sha256
from weedz.manifest import read_manifest
from weedz.region_evaluation.provenance import evaluator_provenance
from weedz.species_benchmark import FrameBatch, RegionBatch, compare_species


class TaxonomyDocument(BaseModel):
    label_kind: Literal["taxon"]
    source: str
    model_labels_sha256: Sha256
    mapping: dict[str, str]


def checked_bytes(path: Path, expected: str) -> bytes:
    with path.open("rb") as stream:
        content = stream.read(128 * 1024 * 1024 + 1)
    if len(content) > 128 * 1024 * 1024:
        raise ValueError(f"Cached input exceeds 128 MiB: {path}")
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError(f"Checksum mismatch: {path}")
    return content


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "frames", "regions", "taxonomy"):
        parser.add_argument(f"--{name}", type=Path, required=True)
        parser.add_argument(f"--{name}-sha256", required=True)
    parser.add_argument("--vocabulary", type=Path, required=True)
    parser.add_argument("--budget", type=int, choices=(1, 5), default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Use a new output namespace; existing evidence is never overwritten")
    samples = read_manifest(args.manifest, args.manifest_sha256)
    frames = FrameBatch.model_validate_json(checked_bytes(args.frames, args.frames_sha256))
    regions = RegionBatch.model_validate_json(checked_bytes(args.regions, args.regions_sha256))
    taxonomy = TaxonomyDocument.model_validate_json(
        checked_bytes(args.taxonomy, args.taxonomy_sha256)
    )
    if frames.manifest_sha256 != args.manifest_sha256:
        raise ValueError("Prediction manifest differs from the pinned source manifest")
    if any(sample.source != taxonomy.source for sample in samples):
        raise ValueError("Taxonomy mapping uses a different source namespace")
    if taxonomy.model_labels_sha256 != frames.model.get("labels_sha256"):
        raise ValueError("Taxonomy mapping uses a different classifier vocabulary")
    vocabulary = checked_bytes(args.vocabulary, taxonomy.model_labels_sha256).decode("utf-8")
    if not set(taxonomy.mapping.values()) <= set(vocabulary.splitlines()):
        raise ValueError("Mapping target is absent from the pinned vocabulary")
    start = time.monotonic()
    comparison = compare_species(samples, frames, regions, taxonomy.mapping, args.budget)
    document = {
        "schema": 1,
        "comparison": comparison,
        "aggregation_seconds": time.monotonic() - start,
        "new_inference_calls": 0,
        "inputs": {
            name: {"path": str(getattr(args, name)), "sha256": getattr(args, f"{name}_sha256")}
            for name in ("manifest", "frames", "regions", "taxonomy")
        },
        "models": {"frames": frames.model, "regions": regions.model},
        "evaluator": evaluator_provenance(),
        "producer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "limitations": [
            "Previously inspected development cohort; no fresh holdout or NZ performance claim",
            "Partial source labels: positive recall only; no precision, F1 or negative accuracy",
            "Same checkpoint and vocabulary; crop policies, compute and recorded runtimes differ",
            "Max-score uses cached top-five lists; scores are not calibrated presence confidence",
            "Image-level hits do not establish correct plant localization",
            "Unbounded candidate union is coverage diagnostic only, not a final output method",
            "All original classifier taxa remain eligible; no ground-truth vocabulary restriction",
            "No source media decoded here; use closed region evaluation to verify actual pixels",
        ],
    }
    args.output.mkdir(parents=True, mode=0o700)
    receipt = write_receipt(args.output, "report.json", document)
    print(receipt["sha256"])
    print(comparison["methods"])


if __name__ == "__main__":
    main()
