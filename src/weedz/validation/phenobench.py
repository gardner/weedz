"""PhenoBench's fixed 64-image publisher-validation development cohort."""

import hashlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from weedz.labelled.archive import SourceArchive
from weedz.region_evaluation.geometry import mask_overlap
from weedz.region_evaluation.matching import match_regions
from weedz.region_evaluation.proposal_masks import proposal_mask
from weedz.validation.agri import (
    BoolMask,
    Tallies,
    configuration,
    image_coverage,
    mask_union,
    materialize,
    select,
)
from weedz.validation.agri_models import (
    model_inputs,
    release_cuda,
    sam_configuration,
    sam_predictor,
)
from weedz.validation.cocostuff_data import Download, verified_download
from weedz.validation.gates import apply_development_gates, cohort_sha256, prefixed
from weedz.validation.registry import Check, RunContext, register
from weedz.validation.scorecard import CheckResult
from weedz.validation.splits import split_of

NAME = "phenobench-instance-recovery"
ARCHIVE = Download(
    "https://www.phenobench.org/data/PhenoBench-v110.zip",
    "a310c1c1dcfec4ca4897097fd38c02af39ea24112f658fd9408d5deb3c7c8bfc",
)
SELECTION_SALT = "weedz-phenobench-development64-v1:"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Plant:
    category: str
    native_id: int
    partial: bool
    mask: BoolMask


def instances(semantics: np.ndarray, ids: np.ndarray) -> list[Plant]:
    if semantics.shape != ids.shape or semantics.ndim != 2:
        raise ValueError("Semantic and instance masks must share a two-dimensional grid")
    if not set(np.unique(semantics)) <= {0, 1, 2, 3, 4}:
        raise ValueError("Unknown PhenoBench semantic ID")
    result = []
    for category, values in (("crop", (1, 3)), ("weed", (2, 4))):
        group = np.isin(semantics, values)
        for native_id in np.unique(ids[group]):
            if native_id > 0:
                mask = (ids == native_id) & group
                result.append(
                    Plant(category, int(native_id), bool((semantics[mask] >= 3).any()), mask)
                )
    return result


def size_stratum(pixels: int) -> str:
    if pixels < 512:
        return "under512"
    return "512to2047" if pixels < 2048 else "2048plus"


def score_image(
    tally: Tallies, semantics: np.ndarray, ids: np.ndarray, proposals: list[BoolMask], date: str
) -> None:
    plants = instances(semantics, ids)
    overlaps = [[mask_overlap(plant.mask, mask).iou or 0 for mask in proposals] for plant in plants]
    matched = match_regions(overlaps, threshold=0.5, proposal_count=len(proposals))
    hits = {match.truth for match in matched.matches}
    for index, plant in enumerate(plants):
        tally.add(
            "instance_recall",
            index in hits,
            (
                "all",
                plant.category,
                f"size:{size_stratum(int(plant.mask.sum()))}",
                f"date:{date}",
                "partial" if plant.partial else "complete",
            ),
        )
    union = mask_union(proposals, semantics.shape)
    for stratum, truth in (
        ("all", semantics > 0),
        (f"date:{date}", semantics > 0),
        ("crop", np.isin(semantics, (1, 3))),
        ("weed", np.isin(semantics, (2, 4))),
    ):
        image_coverage(tally, truth, union, stratum)
    overlap = mask_overlap(semantics > 0, union)
    if overlap.iou is not None:
        tally.fractions["foreground_iou"].append(overlap.iou)


def load_items(context: RunContext) -> tuple[list[tuple[str, Path, Path, Path]], dict[str, str]]:
    relative = Path("phenobench/source/PhenoBench-v110.zip")
    archive = verified_download(ARCHIVE, context.data_root / relative)
    inputs = {str(relative): ARCHIVE.sha256}
    result = []
    with SourceArchive(archive, ARCHIVE.sha256, maximum_members=30000) as source:
        mapping = {tuple(Path(name).parts[-3:]): name for name in source.members}
        names = [key[2] for key in mapping if key[:2] == ("val", "images")]
        names.sort(key=lambda name: hashlib.sha256((SELECTION_SALT + name).encode()).hexdigest())
        for name in select(names[:64], context.limit):
            paths = [
                materialize(
                    context.data_root,
                    Path("phenobench") / kind / name,
                    source.read(mapping["val", kind, name]),
                    inputs,
                )
                for kind in ("images", "semantics", "plant_instances")
            ]
            result.append((name, *paths))
    return result, inputs


def run(context: RunContext, predict: Callable[[Path], list[dict]] | None = None) -> CheckResult:
    items, inputs = load_items(context)
    inputs.update(model_inputs(context.data_root))
    predict = predict or sam_predictor(context, "phenobench")
    tally = Tallies()
    halves = {split: Tallies() for split in ("development", "held-out")}
    proposals = 0
    for index, (name, image, semantic, instance) in enumerate(items, 1):
        with Image.open(semantic) as source:
            semantics = np.asarray(source)
        with Image.open(instance) as source:
            ids = np.asarray(source)
        records = predict(image)
        proposals += len(records)
        masks = [
            proposal_mask(row, size=(semantics.shape[1], semantics.shape[0]), kind="sam3")
            for row in records
        ]
        score_image(tally, semantics, ids, masks, name.split("_")[0])
        score_image(halves[split_of(name)], semantics, ids, masks, name.split("_")[0])
        logger.info("PhenoBench %d/%d", index, len(items))
    del predict
    release_cuda()
    metrics = tally.metrics()
    for split, counts in halves.items():
        metrics.extend(prefixed(counts.metrics(), split))
    config = configuration(context)
    config["cohort_sha256"] = cohort_sha256((name, split_of(name)) for name, *_ in items)
    config["gate_split_policy"] = "split_of(source_id); pooled validation rows are diagnostic"
    limits = [
        "Gates use source-ID development and held-out halves of the previously inspected "
        "64-photo cohort; this is not fresh independent held-out evidence."
    ]
    metrics = apply_development_gates(
        metrics,
        metrics,
        ("instance_recall", "foreground_half_covered"),
        config,
        limits,
        development_stratum="development",
        held_out_stratum="held-out",
    )
    return CheckResult(
        check=NAME,
        stage="region-proposals",
        dataset="PhenoBench v1.1.0 development64",
        split="validation",
        metrics=metrics,
        inputs=inputs,
        configuration={
            **config,
            **sam_configuration(),
            **tally.means(),
            "images": len(items),
            "proposals": proposals,
            "instance_iou_threshold": 0.5,
            "selection": f"lowest 64 SHA256({SELECTION_SALT}filename), publisher val",
            "proposal_budget": "all retained (128 per prompt)",
            "size_strata_pixels": "under512, 512to2047, 2048plus",
        },
        limits=[
            *limits,
            "Already inspected during development; the fixed 64-image publisher validation subset "
            "is not a fresh held-out cohort. No parameters were tuned in this port.",
            "Source semantics: 0 background, 1 crop, 2 weed, 3 partial crop, 4 partial weed. "
            "The website repeats partial-crop for ID 4; the publisher devkit confirms "
            "partial weed.",
            "SAM3 is class-agnostic: crop/weed strata measure localization, not semantic "
            "recognition. These labels cannot measure weed-species identity.",
            "Instance IDs are scoped by crop/weed group; partial plants are included. "
            "Foreground without an instance ID contributes only to foreground coverage.",
            "One-to-one maximum-cardinality mask IoU matching at 0.5. Instance Wilson intervals "
            "ignore dependence within images; image-coverage intervals use one trial per image.",
            "The archive says CC BY-NC-SA 4.0; website/devkit say CC BY-SA 4.0. "
            "Retain private noncommercial research handling. Pretraining overlap is unknown.",
        ],
    )


register(
    Check(
        NAME,
        "region-proposals",
        "PhenoBench development64",
        run,
        "Source plant instance recovery and image-level foreground coverage",
    )
)
