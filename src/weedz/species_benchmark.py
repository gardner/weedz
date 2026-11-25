"""Positive-only development comparison of cached same-checkpoint predictions."""

from collections import Counter

from pydantic import BaseModel, JsonValue, TypeAdapter

from weedz.contract import Sample, Sha256
from weedz.species_aggregation import RankedTaxon, aggregate_taxa


class CropRanking(BaseModel):
    topk: list[RankedTaxon]


class FramePrediction(BaseModel):
    sample_id: str
    image_sha256: Sha256
    frame_topk: list[RankedTaxon]
    tiles: list[CropRanking]


class RegionPrediction(BaseModel):
    source_id: str
    image_sha256: Sha256
    regions: list[CropRanking]


class FrameBatch(BaseModel):
    model: dict[str, JsonValue]
    manifest_sha256: Sha256
    predictions: list[FramePrediction]


class RegionBatch(BaseModel):
    model: dict[str, JsonValue]
    manifest_sha256: Sha256
    predictions: list[RegionPrediction]


def _validate_cohort(samples: list[Sample], frames: FrameBatch, regions: RegionBatch) -> None:
    if not samples or frames.manifest_sha256 != regions.manifest_sha256:
        raise ValueError("Nonempty common manifest required")
    ids = [sample.id for sample in samples]
    if len({sample.media.sha256 for sample in samples}) != len(samples):
        raise ValueError("Duplicate encoded image assets cannot inflate the benchmark")
    frame_ids = [row.sample_id for row in frames.predictions]
    region_ids = [row.source_id for row in regions.predictions]
    for identities in (ids, frame_ids, region_ids):
        if len(set(identities)) != len(identities) or set(identities) != set(ids):
            raise ValueError("Duplicate, missing or extra sample identities")
    for key in ("weights_sha256", "labels_sha256"):
        identity = frames.model.get(key)
        TypeAdapter(Sha256).validate_python(identity)
        if identity != regions.model.get(key):
            raise ValueError(f"Same recorded classifier {key} required")


def _source_taxa(sample: Sample, mapping: dict[str, str]) -> set[str]:
    taxa = {
        note.taxon
        for note in sample.annotations
        if note.origin == "source"
        and note.label == "present"
        and note.review not in {"rejected", "uncertain"}
        and note.taxon is not None
    }
    if not taxa:
        raise ValueError(f"No source-positive species labels for {sample.id}")
    if not taxa <= mapping.keys():
        raise ValueError(f"Incomplete taxonomy mapping for {sample.id}")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Taxonomy mapping must not merge source species")
    return taxa


def compare_species(
    samples: list[Sample],
    frames: FrameBatch,
    regions: RegionBatch,
    mapping: dict[str, str],
    budget: int,
) -> dict:
    """Score only explicit source positives; no precision or exhaustive-negative claim.

    Ranking sees every cached candidate, never the source taxonomy or target list.
    Checkpoint identity is shared, but crop policies, runtimes and compute may differ.
    """
    _validate_cohort(samples, frames, regions)
    frame_rows = {row.sample_id: row for row in frames.predictions}
    region_rows = {row.source_id: row for row in regions.predictions}
    rows = []
    for sample in samples:
        frame, region = frame_rows[sample.id], region_rows[sample.id]
        if frame.image_sha256 != sample.media.sha256 or region.image_sha256 != sample.media.sha256:
            raise ValueError(f"Prediction pixel-asset identity mismatch for {sample.id}")
        crops = {
            "tiles": [r.topk for r in frame.tiles],
            "regions": [r.topk for r in region.regions],
        }
        rankings = {
            "whole_frame": aggregate_taxa([frame.frame_topk], policy="max_score", budget=budget)
        }
        for branch, lists in crops.items():
            for policy in ("frequency", "max_score"):
                rankings[f"{branch}_{policy}"] = aggregate_taxa(lists, policy=policy, budget=budget)
        # Source labels enter only after rankings have been fixed.
        truth = _source_taxa(sample, mapping)
        hits = {
            method: sorted(taxon for taxon in truth if mapping[taxon] in predicted)
            for method, predicted in rankings.items()
        }
        available = {
            branch: sorted(
                taxon
                for taxon in truth
                if any(prediction.taxon == mapping[taxon] for crop in lists for prediction in crop)
            )
            for branch, lists in crops.items()
        }
        rows.append(
            {
                "sample_id": sample.id,
                "image_sha256": sample.media.sha256,
                "source_positive_taxa": sorted(truth),
                "rankings": rankings,
                "hits": hits,
                "available_positive_taxa": available,
                "crop_counts": {branch: len(lists) for branch, lists in crops.items()},
            }
        )
    return _summarize(rows, budget)


def _summarize(rows: list[dict], budget: int) -> dict:
    denominator = sum(len(row["source_positive_taxa"]) for row in rows)
    methods = {
        method: {
            "recovered_positive_pairs": count,
            "positive_pair_recall": count / denominator,
            "images_with_any_hit": sum(bool(row["hits"][method]) for row in rows),
        }
        for method in rows[0]["rankings"]
        for count in [sum(len(row["hits"][method]) for row in rows)]
    }
    taxa = Counter(taxon for row in rows for taxon in row["source_positive_taxa"])
    return {
        "images": len(rows),
        "positive_image_taxon_pairs": denominator,
        "final_taxon_budget_per_image": budget,
        "methods": methods,
        "candidate_coverage": {
            branch: {
                "available_positive_pairs": sum(
                    len(row["available_positive_taxa"][branch]) for row in rows
                ),
                "actual_crops": sum(row["crop_counts"][branch] for row in rows),
            }
            for branch in ("tiles", "regions")
        },
        "by_source_taxon": {
            taxon: {
                "positive_images": taxa[taxon],
                "recovered": {
                    method: sum(taxon in row["hits"][method] for row in rows) for method in methods
                },
            }
            for taxon in sorted(taxa)
        },
        "rows": rows,
    }
