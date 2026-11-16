"""Private source-labelled region evaluation; this command never invokes inference."""

import argparse
import hashlib
from pathlib import Path

from weedz.annotation.semantic import proposer_semantic
from weedz.batches.receipts import write_receipt
from weedz.manifest import read_manifest
from weedz.region_evaluation.aggregate import aggregate_boxes
from weedz.region_evaluation.boxes import BUDGETS, THRESHOLDS, box_report
from weedz.region_evaluation.classifier_inputs import load_classifier
from weedz.region_evaluation.proposal_inputs import load_proposals
from weedz.region_evaluation.provenance import evaluator_provenance
from weedz.region_evaluation.semantic import sparse_report
from weedz.region_evaluation.sparse_aggregate import aggregate_sparse
from weedz.region_evaluation.taxonomy import load_taxonomy
from weedz.segmentation.ingress import proposal_metadata


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--mode", choices=("sparse", "boxes"), default="sparse")
    command.add_argument("--truth-origin", choices=("source", "reviewer"), default="source")
    for name in ("manifest", "assets-root", "proposals-ready", "output"):
        command.add_argument(f"--{name}", required=True, type=Path)
    command.add_argument("--manifest-sha256", required=True)
    command.add_argument("--ready-sha256", required=True)
    command.add_argument("--proposer", required=True, choices=("sam2", "sam3"))
    command.add_argument("--max-source-bytes", type=int, default=None)
    command.add_argument("--allow-source-subset", action="store_true")
    command.add_argument("--classifier", type=Path)
    command.add_argument("--classifier-sha256")
    command.add_argument("--taxonomy-map", type=Path)
    command.add_argument("--taxonomy-map-sha256")
    command.add_argument("--vocabulary", type=Path)
    return command


def _inputs(args):
    samples = read_manifest(args.manifest, args.manifest_sha256)
    batch = load_proposals(
        args.proposals_ready, args.ready_sha256, samples, allow_subset=args.allow_source_subset
    )
    expected = "SAM2.1" if args.proposer == "sam2" else "SAM3"
    for row in batch.rows.values():
        if proposer_semantic(row["segmentation"]["provenance"])[1] != expected:
            raise ValueError("Declared proposer differs from its stored model profile")
    classifier, taxonomy = _identification(args, samples, batch)
    return samples, batch, classifier, taxonomy


def _identification(args, samples, batch):
    supplied = (
        args.classifier,
        args.classifier_sha256,
        args.taxonomy_map,
        args.taxonomy_map_sha256,
        args.vocabulary,
    )
    if not any(supplied):
        return None, None
    if not all(supplied) or args.mode != "boxes":
        raise ValueError("Box identification needs a pinned classifier, mapping and vocabulary")
    classifier = load_classifier(
        args.classifier,
        args.classifier_sha256,
        samples,
        batch,
        allow_subset=args.allow_source_subset,
    )
    taxonomy = load_taxonomy(
        args.taxonomy_map, args.taxonomy_map_sha256, args.vocabulary, classifier
    )
    return classifier, taxonomy


def main() -> None:
    args = parser().parse_args()
    samples, batch, classifier, taxonomy = _inputs(args)
    if args.mode == "boxes":
        cases = box_report(
            samples,
            args.assets_root,
            batch,
            classifier=classifier,
            taxonomy=taxonomy,
            max_source_bytes=args.max_source_bytes,
            truth_origin=args.truth_origin,
        )
        aggregate = aggregate_boxes(cases)
    else:
        cases = sparse_report(
            samples,
            args.assets_root,
            batch,
            kind=args.proposer,
            max_source_bytes=args.max_source_bytes,
            truth_origin=args.truth_origin,
        )
        aggregate = aggregate_sparse(cases)
    references = []
    for case in cases:
        key = hashlib.sha256(case["sample_id"].encode("utf-8")).hexdigest()
        references.append(write_receipt(args.output, f"cases/{key}.json", case))
    document = {
        "schema": 2,
        "label_manifest_sha256": args.manifest_sha256,
        "inference_manifest_sha256": batch.manifest_sha256,
        "ready_sha256": batch.ready_sha256,
        "proposals_sha256": batch.proposals_sha256,
        "model_version": batch.model_version,
        "source_sample_count": batch.source_sample_count,
        "sample_count": len(cases),
        "excluded_source_sample_ids": batch.excluded_sample_ids,
        "cases": references,
        "aggregate": aggregate,
        "protocol": _protocol(args.mode, args.truth_origin, classifier is not None),
        "evaluator": evaluator_provenance(),
        "interpretation": (
            "Diagnostics only; no fresh holdout, training-exclusion or independent NZ gold claim"
        ),
        **proposal_metadata({}, args.max_source_bytes),
    }
    if classifier is not None and taxonomy is not None:
        document["classifier"] = {
            "sha256": classifier.sha256,
            "manifest_sha256": classifier.manifest_sha256,
            "model_version": classifier.model_version,
            "metadata": classifier.metadata,
            "mapping_sha256": taxonomy.sha256,
            "vocabulary_sha256": taxonomy.vocabulary_sha256,
            "source_sample_count": classifier.source_sample_count,
            "excluded_source_sample_ids": classifier.excluded_sample_ids,
        }
    reference = write_receipt(args.output, "report.json", document)
    print(reference["sha256"])


def _protocol(mode: str, origin: str, with_classifier: bool) -> dict:
    return {
        "revision": 1,
        "truth_origin": origin,
        "task": "detection" if mode == "boxes" else "sparse_segmentation",
        "unit": "publisher-labelled region" if mode == "boxes" else "labelled positive pixel",
        "proposal_budgets": BUDGETS,
        "proposal_order": "unchanged stored order",
        "iou_thresholds": THRESHOLDS if mode == "boxes" else None,
        "matching": (
            "deterministic maximum-cardinality threshold; taxonomy independent; not COCO AP"
            if mode == "boxes"
            else None
        ),
        "classification": (
            "fixed masked view, first returned taxon; explicit vocabulary mapping"
            if with_classifier
            else None
        ),
        "negative_evidence": (
            "only documented exhaustive source or accepted reviewer task/target scope"
        ),
        "unassessed": (
            "unlabelled/partial scope is not a negative; model masks are never ground truth"
        ),
    }


if __name__ == "__main__":
    main()
