"""Partial ImageWeeds boxes: localization, conditional ID and positive species pairs."""

import hashlib
import json
import logging
import math
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from itertools import batched
from pathlib import Path

from PIL import Image
from pydantic import BaseModel

from weedz.contract import Annotation
from weedz.discovery.inference import square_view
from weedz.labelled.archive import SourceArchive
from weedz.labelled.images import prepare_image
from weedz.labelled.imageweeds import PROFILES, source_boxes, source_rights
from weedz.region_evaluation.geometry import Box, box_iou
from weedz.region_evaluation.matching import Matching, match_regions
from weedz.segmentation.sam3_image import restore_concept_regions
from weedz.species_aggregation import RankedTaxon, aggregate_taxa
from weedz.validation.agri import Tallies, configuration, materialize, select
from weedz.validation.agri_models import (
    BATCH_SIZE,
    MAX_BYTES,
    SAM_CONFIG,
    TOP_K,
    cache_key,
    identity,
    model_inputs,
    plant_predictor,
    proposal_batch,
    release_cuda,
    sam_configuration,
)
from weedz.validation.cocostuff_data import Download, atomic_file, verified_download
from weedz.validation.fingerprint import require_stored_orientation
from weedz.validation.gates import apply_development_gates, cohort_sha256, hash_split_metrics
from weedz.validation.metrics import Rate
from weedz.validation.registry import Check, RunContext, register
from weedz.validation.scorecard import CheckResult
from weedz.validation.splits import split_of

REGIONS = "imageweeds-region-recovery"
SPECIES = "imageweeds-species"
BUDGET = 100
IOU = 0.5
logger = logging.getLogger(__name__)
LIMITS = [
    "Already inspected during development. Publisher split unavailable; all 138 eligible "
    "images retain pooled validation diagnostics. Gates use split_of(source_id) halves, "
    "not a fresh independent held-out claim.",
    "Partial publisher boxes establish labelled positives only. Unmatched proposals and "
    "unlabelled species are unassessed; no precision or false-alarm rate is supported.",
    "All decoded-pixel aliases are quarantined, including conflicting annotation aliases. "
    "An image with any invalid source box is withheld whole; no clipping or label union.",
    "Box matching is one-to-one maximum cardinality at IoU >=0.5 in the first 100 retained "
    "SAM3 proposals. Boxes do not establish individual plant or mask accuracy.",
    "Region and image-species-pair Wilson intervals ignore dependence within photographs. "
    "No independently established site split or pretraining exclusion. ImageWeeds is CC BY 4.0.",
]


@dataclass(frozen=True)
class Item:
    source_id: str
    image: Path
    sha256: str
    pixel_sha256: str
    crop: str
    boxes: tuple[Annotation, ...]


class SpeciesEvidence(BaseModel):
    regions: list[dict]
    tight: list[list[RankedTaxon]]
    masked: list[list[RankedTaxon]]


def label_boxes(native: dict, image: dict) -> tuple[Annotation, ...]:
    return source_boxes(image, native["annotations"], native["categories"])


def primary_items(items: Sequence[Item]) -> tuple[list[Item], int]:
    counts = Counter(item.pixel_sha256 for item in items)
    kept = [item for item in items if counts[item.pixel_sha256] == 1]
    return kept, len(items) - len(kept)


def _native_items(
    source: SourceArchive, crop: str, context: RunContext, inputs: dict[str, str]
) -> tuple[list[Item], set[str]]:
    raw = source.read("weedcoco.json", maximum_bytes=10_000_000)
    materialize(context.data_root, Path(f"imageweeds/labels/{crop}.json"), raw, inputs)
    native = json.loads(raw)
    items, invalid_pixels = [], set()
    for image in native["images"]:
        source_rights(native, image)
        raw = source.read(f"images/{image['file_name']}", maximum_bytes=20_000_000)
        prepared = prepare_image(raw, (image["width"], image["height"]), "original-jpeg")
        try:
            boxes = label_boxes(native, image)
        except ValueError as error:
            if str(error) != "Source box outside image bounds":
                raise
            invalid_pixels.add(prepared.pixel_sha256)
            continue
        path = materialize(
            context.data_root, Path("imageweeds/images") / crop / image["file_name"], raw, inputs
        )
        items.append(
            Item(
                f"{crop}/{image['file_name']}",
                path,
                hashlib.sha256(raw).hexdigest(),
                prepared.pixel_sha256,
                crop,
                boxes,
            )
        )
    return items, invalid_pixels


def load_items(context: RunContext) -> tuple[list[Item], dict[str, str], int]:
    inputs: dict[str, str] = {}
    items: list[Item] = []
    invalid: set[str] = set()
    for crop, (uuid, digest, _) in PROFILES.items():
        download = Download(f"https://weed-ai.sydney.edu.au/code/download/{uuid}.zip", digest)
        relative = Path(f"imageweeds/source/imageweeds-{crop}.zip")
        path = verified_download(download, context.data_root / relative)
        inputs[str(relative)] = digest
        with SourceArchive(path, digest) as source:
            candidates, excluded = _native_items(source, crop, context, inputs)
            items.extend(candidates)
            invalid.update(excluded)
    primary, aliases = primary_items(items)
    primary = [item for item in primary if item.pixel_sha256 not in invalid]
    return select(primary, context.limit), inputs, aliases


def matching(item: Item, regions: list[dict]) -> Matching:
    proposals: list[Box] = [tuple(row["box"]) for row in regions[:BUDGET]]
    overlaps = [
        [box_iou(note.box, box) for box in proposals] for note in item.boxes if note.box is not None
    ]
    return match_regions(overlaps, threshold=IOU, proposal_count=len(proposals))


def _strata(item: Item, note: Annotation) -> tuple[str, ...]:
    return "all", f"crop:{item.crop}", f"taxon:{note.taxon}"


def region_metrics(items: Sequence[Item], predict: Callable[[Item], list[dict]]) -> list[Rate]:
    tally = Tallies()
    for item in items:
        hits = {match.truth for match in matching(item, predict(item)).matches}
        for index, note in enumerate(item.boxes):
            tally.add("box_recall", index in hits, _strata(item, note))
    return tally.metrics()


def canonical(taxon: str) -> str:
    """Match the five explicit source binomials to full PlantCLEF names with authors."""
    return " ".join(taxon.split()[:2])


def _region_species(tally: Tallies, item: Item, evidence: SpeciesEvidence) -> None:
    if len(evidence.tight) != len(item.boxes) or len(evidence.masked) != len(evidence.regions):
        raise ValueError("Classifier evidence and source/proposal counts disagree")
    matched = {match.truth: match.proposal for match in matching(item, evidence.regions).matches}
    for index, note in enumerate(item.boxes):
        strata = _strata(item, note)
        tight = [canonical(row.taxon) for row in evidence.tight[index]]
        tally.add("source_box_top1", bool(tight) and tight[0] == note.taxon, strata)
        tally.add("source_box_top5", note.taxon in tight, strata)
        correct = False
        if index in matched:
            names = [canonical(row.taxon) for row in evidence.masked[matched[index]]]
            correct = bool(names) and names[0] == note.taxon
            tally.add("conditional_top1", correct, strata)
            tally.add("conditional_top5", note.taxon in names, strata)
        tally.add("localized_and_identified", correct, strata)


def species_metrics(
    items: Sequence[Item], predict: Callable[[Item], SpeciesEvidence]
) -> list[Rate]:
    tally = Tallies()
    for name in ("conditional_top1", "conditional_top5"):
        tally.counts[name, "all"] = [0, 0]
    for index, item in enumerate(items, 1):
        evidence = predict(item)
        _region_species(tally, item, evidence)
        logger.info("ImageWeeds species %d/%d", index, len(items))
        for policy in ("frequency", "max_score"):
            names = {
                canonical(name)
                for name in aggregate_taxa(evidence.masked, policy=policy, budget=TOP_K)
            }
            for taxon in sorted({note.taxon for note in item.boxes if note.taxon is not None}):
                tally.add(
                    f"image_species_{policy}_at5",
                    taxon in names,
                    ("all", f"crop:{item.crop}", f"taxon:{taxon}"),
                )
    return tally.metrics()


def species_predictor(
    context: RunContext, proposals: dict[str, list[dict]]
) -> Callable[[Item], SpeciesEvidence]:
    model_inputs(context.data_root, species=True)
    stamp = identity(
        "imageweeds",
        "plantclef",
        TOP_K,
        BATCH_SIZE,
        "legacy-tight-and-masked",
        context.device,
        model_inputs(context.data_root, species=True),
    )
    output = context.cache_dir / "agri" / f"species-{stamp}"
    classify = plant_predictor(context)

    def predict(item: Item) -> SpeciesEvidence:
        records = proposals[item.source_id][:BUDGET]
        key = cache_key(item.sha256, records, [note.box for note in item.boxes])
        path = output / f"{key}.json"
        if path.is_file():
            return SpeciesEvidence.model_validate_json(path.read_text())
        require_stored_orientation(item.image)
        raw = item.image.read_bytes()
        if hashlib.sha256(raw).hexdigest() != item.sha256:
            raise ValueError("ImageWeeds image changed during species inference")
        with Image.open(item.image) as source:
            image = source.convert("RGB")
        tight = [
            image.crop(
                (
                    math.floor(note.box[0]),
                    math.floor(note.box[1]),
                    math.ceil(note.box[2]),
                    math.ceil(note.box[3]),
                )
            )
            for note in item.boxes
            if note.box is not None
        ]
        regions = restore_concept_regions(
            raw, records, SAM_CONFIG, expected_sha256=item.sha256, max_source_bytes=MAX_BYTES
        )
        masked = [region.views["masked"] for region in regions]
        views = [*tight, *(square_view(view, (0, 0, *view.size)) for view in masked)]
        ranks = [rank for batch in batched(views, BATCH_SIZE) for rank in classify(list(batch))]
        evidence = SpeciesEvidence(
            regions=records, tight=ranks[: len(tight)], masked=ranks[len(tight) :]
        )
        with atomic_file(path) as stream:
            stream.write(evidence.model_dump_json().encode())
        return evidence

    return predict


def _proposals(
    context: RunContext, items: Sequence[Item]
) -> tuple[dict[str, list[dict]], dict[str, str]]:
    evidence = proposal_batch(context, "imageweeds", [item.image for item in items])
    proposals = {
        item.source_id: records[:BUDGET]
        for item, records in zip(items, evidence.regions, strict=True)
    }
    logger.info("ImageWeeds proposals ready: %d images", len(items))
    return proposals, evidence.runtime


def _result(
    context: RunContext,
    name: str,
    items: list[Item],
    inputs: dict[str, str],
    aliases: int,
    metrics: list[Rate],
    runtime: dict[str, str],
) -> CheckResult:
    species = name == SPECIES
    config = {
        **configuration(context),
        "gate_split_policy": "split_of(source_id); pooled validation rows are diagnostic",
        "cohort_sha256": cohort_sha256(
            (i.source_id, f"{split_of(i.source_id)}/{i.crop}") for i in items
        ),
    }
    limits = list(LIMITS)
    metrics = apply_development_gates(
        metrics,
        metrics,
        ("conditional_top1", "image_species_max_score_at5") if species else ("box_recall",),
        config,
        limits,
        development_stratum="development",
        held_out_stratum="held-out",
    )
    return CheckResult(
        check=name,
        stage="species-identification" if species else "region-proposals",
        dataset="ImageWeeds v2 primary138",
        split="validation",
        metrics=metrics,
        inputs=inputs | model_inputs(context.data_root, species=species),
        configuration={
            **config,
            **sam_configuration(),
            **runtime,
            "images": len(items),
            "boxes": sum(len(item.boxes) for item in items),
            "proposal_budget": BUDGET,
            "box_iou_threshold": IOU,
            "quarantined_alias_records": aliases,
            "invalid_geometry_images": 1,
            "species_budget": TOP_K,
            "classifier_batch_size": BATCH_SIZE,
            "classifier_vocabulary": "full 7806 PlantCLEF classes",
            "source_crop_control": "floor/ceil source box, original tight centre-crop",
            "region_crop": "pipeline masked view, max side 1024, neutral square padding",
            "species_policies": "frequency and max_score, same five-slot budget",
        },
        limits=[
            *limits,
            *(
                [
                    "Conditional identification excludes localization misses; "
                    "localized_and_identified keeps every labelled box in the denominator. "
                    "Image-species pairs count each taxon once per photo. Both aggregation "
                    "policies are descriptive development comparisons.",
                    "BioClipClassifier uses a fixed NZ watchlist vocabulary with none of the five "
                    "ImageWeeds taxa; it cannot measure their species identity. PlantCLEF uses "
                    "its complete vocabulary. Scores are uncalibrated, "
                    "not presence probabilities.",
                ]
                if species
                else []
            ),
        ],
    )


def run_regions(context: RunContext) -> CheckResult:
    items, inputs, aliases = load_items(context)
    proposals, runtime = _proposals(context, items)
    metrics = hash_split_metrics(
        items,
        lambda members: region_metrics(members, lambda item: proposals[item.source_id]),
        lambda item: item.source_id,
    )
    return _result(context, REGIONS, items, inputs, aliases, metrics, runtime)


def run_species(context: RunContext) -> CheckResult:
    items, inputs, aliases = load_items(context)
    proposals, runtime = _proposals(context, items)
    predictor = species_predictor(context, proposals)
    metrics = hash_split_metrics(
        items,
        lambda members, predict=predictor: species_metrics(members, predict),
        lambda item: item.source_id,
    )
    del predictor
    release_cuda()
    return _result(context, SPECIES, items, inputs, aliases, metrics, runtime)


register(
    Check(
        REGIONS,
        "region-proposals",
        "ImageWeeds v2",
        run_regions,
        "Recovery of partial publisher-labelled boxes",
    )
)
register(
    Check(
        SPECIES,
        "species-identification",
        "ImageWeeds v2",
        run_species,
        "Conditional PlantCLEF ID and labelled image-species pair recovery at five slots",
    )
)
