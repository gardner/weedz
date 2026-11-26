"""Frozen COCO-Stuff val2017 vegetation presence and region proposal checks."""

import logging
import math
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from weedz.region_evaluation.proposal_masks import proposal_mask
from weedz.segmentation.sam3_image import CODE_REVISION
from weedz.validation.cocostuff_data import (
    SIZE_STRATA,
    VEGETATION,
    VOID_TOLERANCE,
    Dataset,
    ImageItem,
    Stratum,
    dataset,
    instance_mask,
)
from weedz.validation.cocostuff_models import (
    SAM_CONFIG,
    SamPredictor,
    model_inputs,
    release_cuda,
    sam_predictor,
    sam_presence,
    segformer_predictor,
)
from weedz.validation.cocostuff_regions import (
    BACKGROUND_THRESHOLD,
    PROPOSAL_LIMIT,
    REGION_THRESHOLD,
    ProposalCounts,
    score_proposals,
)
from weedz.validation.metrics import Outcome, Rate, binary_metrics, rate
from weedz.validation.registry import Check, RunContext, register
from weedz.validation.scorecard import CheckResult
from weedz.validation.splits import Split

logger = logging.getLogger(__name__)
DATASET = "COCO-Stuff val2017"
PRESENCE = "cocostuff-vegetation-presence"
PROPOSALS = "cocostuff-vegetation-proposals"
RECALL_TARGET = 0.95
FALSE_ALARM_CEILING = 0.10
COMMON_LIMITS = [
    "COCO-Stuff PNG index 255 is void; index 0 is person. Label ID 0 is void only in labels.txt.",
    "Vegetation follows the selected scene labels. Fruit and vegetable food classes are excluded "
    "because they describe food objects, including detached produce, rather than scene vegetation.",
    "COCO and COCO-Stuff annotations are CC BY 4.0. COCO images are subject to Flickr terms.",
    "This evaluation measures COCO label recovery. COCO val2017 may overlap SAM3 training data.",
]


@dataclass(frozen=True)
class PresenceItem:
    source_id: str
    stratum: Stratum
    split: Split

    @property
    def positive(self) -> bool:
        return self.stratum in SIZE_STRATA


@dataclass(frozen=True)
class PresencePrediction:
    score: float
    baseline_positive: bool


def presence_metrics(
    items: Sequence[PresenceItem], predict: Callable[[PresenceItem], PresencePrediction]
) -> tuple[float | None, list[Rate]]:
    predictions = {
        item.source_id: predict(item) for item in items if item.stratum != "unassessable"
    }
    positive_scores = sorted(
        (
            predictions[item.source_id].score
            for item in items
            if item.split == "development" and item.positive
        ),
        reverse=True,
    )
    threshold = (
        positive_scores[math.ceil(RECALL_TARGET * len(positive_scores)) - 1]
        if positive_scores
        else None
    )
    held_out = [
        item for item in items if item.split == "held-out" and item.stratum != "unassessable"
    ]
    tuned = _presence_rates(
        held_out if threshold is not None else [],
        lambda item: threshold is not None and predictions[item.source_id].score >= threshold,
    )
    baseline = _presence_rates(held_out, lambda item: predictions[item.source_id].baseline_positive)
    return threshold, [*tuned, *_prefix_rates("baseline", baseline)]


def _prefix_rates(prefix: str, rates: list[Rate]) -> list[Rate]:
    return [row.model_copy(update={"name": f"{prefix}_{row.name}"}) for row in rates]


def _presence_rates(
    items: Sequence[PresenceItem], decide: Callable[[PresenceItem], bool]
) -> list[Rate]:
    outcomes = [
        Outcome(
            item=item.source_id,
            truth=item.positive,
            predicted=decide(item),
            stratum=item.stratum if item.positive else None,
        )
        for item in items
    ]
    measured = {
        (row.name, row.stratum): row
        for row in binary_metrics(
            outcomes,
            target_recall=RECALL_TARGET,
            false_alarm_ceiling=FALSE_ALARM_CEILING,
        )
    }
    recall = [
        measured.get(("recall", size)) or rate("recall", 0, 0, stratum=size, target=RECALL_TARGET)
        for size in ("all", *SIZE_STRATA)
    ]
    false_alarms = measured.get(("false_alarm_rate", "all")) or rate(
        "false_alarm_rate",
        0,
        0,
        ceiling=FALSE_ALARM_CEILING,
    )
    return [*recall, false_alarms]


def _selected(data: Dataset, context: RunContext, splits: Iterable[Split]) -> list[ImageItem]:
    if context.limit is not None and context.limit < 1:
        raise ValueError("The image limit must be positive")
    selection = set(splits)
    if context.limit is None:
        return [item for item in data.items if item.split in selection]
    # For presence, cap the whole run while keeping development and held-out samples.
    quotas = {"development": context.limit // 2, "held-out": context.limit}
    if "development" in selection:
        quotas["held-out"] -= quotas["development"]
    return [
        item
        for split in sorted(selection)
        for item in [candidate for candidate in data.items if candidate.split == split][
            : quotas[split]
        ]
    ]


def _progress(label: str, size: int, index: int) -> None:
    if index % 100 == 0 or index == size:
        logger.info("%s %d/%d", label, index, size)


def _predict_presence(
    data: Dataset,
    items: list[PresenceItem],
    by_id: dict[str, ImageItem],
    name: str,
    predictor: Callable[[Path], PresencePrediction],
) -> tuple[float | None, list[Rate]]:
    index = 0
    total = sum(item.stratum != "unassessable" for item in items)

    def predict(item: PresenceItem) -> PresencePrediction:
        nonlocal index
        result = predictor(data.image(by_id[item.source_id]))
        index += 1
        _progress(name, total, index)
        return result

    threshold, metrics = presence_metrics(items, predict)
    return threshold, _prefix_rates(name, metrics)


def _segformer(
    context: RunContext, data: Dataset, items: list[PresenceItem], by_id: dict[str, ImageItem]
) -> tuple[float | None, list[Rate]]:
    predictor = segformer_predictor(context)

    def predict(path: Path) -> PresencePrediction:
        fraction = predictor(path)
        return PresencePrediction(fraction, fraction > 0)

    return _predict_presence(data, items, by_id, "segformer", predict)


def _sam_presence(
    context: RunContext, data: Dataset, items: list[PresenceItem], by_id: dict[str, ImageItem]
) -> tuple[float | None, list[Rate]]:
    predictor = sam_predictor(context)

    def predict(path: Path) -> PresencePrediction:
        result = predictor(path)
        return PresencePrediction(sam_presence(result), bool(result["regions"]))

    return _predict_presence(data, items, by_id, "sam3", predict)


def _configuration(context: RunContext) -> dict[str, str | int | float | bool]:
    return {
        "device": context.device,
        "vegetation_classes": ", ".join(sorted(VEGETATION)),
        "image_and_region_area_strata": "tiny ≤0.5%, small ≤2%, medium ≤10%, large >10%",
        "sam3_prompts": ", ".join(SAM_CONFIG.prompts),
        "sam3_code_revision": CODE_REVISION,
        "sam3_concept_threshold": SAM_CONFIG.concept_threshold,
        "sam3_max_side": SAM_CONFIG.max_side,
        "sam3_min_area": SAM_CONFIG.min_area,
        "sam3_context_fraction": SAM_CONFIG.context_fraction,
        "sam3_max_regions_per_prompt": SAM_CONFIG.max_regions,
        "sam3_max_prompt_bytes": SAM_CONFIG.max_prompt_bytes,
    }


def run_presence(context: RunContext) -> CheckResult:
    with dataset(context) as data:
        selected = _selected(data, context, ("development", "held-out"))
        by_id = {item.source_id: item for item in selected}
        items = [
            PresenceItem(item.source_id, data.masks(item).stratum, item.split) for item in selected
        ]
        seg_threshold, seg_metrics = _segformer(context, data, items, by_id)
        release_cuda()
        sam_threshold, sam_metrics = _sam_presence(context, data, items, by_id)
        release_cuda()
        excluded = Counter(item.split for item in items if item.stratum == "unassessable")
        return CheckResult(
            check=PRESENCE,
            stage="plant-presence",
            dataset=DATASET,
            split="held-out",
            metrics=seg_metrics + sam_metrics,
            inputs=data.inputs | model_inputs(presence=True),
            configuration={
                **_configuration(context),
                "selected_images": len(items),
                "held_out_images": sum(item.split == "held-out" for item in items),
                "held_out_unassessable": excluded["held-out"],
                "development_unassessable": excluded["development"],
                "negative_void_tolerance": VOID_TOLERANCE,
                "development_positive_recall_target": RECALL_TARGET,
                "development_positive_images": sum(
                    item.split == "development" and item.positive for item in items
                ),
                "segformer_threshold": seg_threshold if seg_threshold is not None else "unmeasured",
                "sam3_presence_threshold": sam_threshold
                if sam_threshold is not None
                else "unmeasured",
                "score_rule": (
                    "score >= threshold. SAM3 uses max raw concept score before retention."
                ),
                "segformer_baseline_rule": "Any predicted ADE20K vegetation pixel",
                "sam3_baseline_rule": "Any proposal retained at the pipeline's fixed cutoff",
            },
            limits=[
                *COMMON_LIMITS,
                "The pinned SegFormer model metadata lists ADE20K (scene_parse_150) fine-tuning, "
                "with no reported COCO fine-tuning. Cross-dataset image duplicates and pretraining "
                "overlap were not audited.",
                "A negative contains no mapped vegetation and at most 2% void. Plants can still "
                "be present in the void area or outside the mapped taxonomy.",
            ],
        )


def _score_images(data: Dataset, items: Sequence[ImageItem], predict: SamPredictor) -> list[Rate]:
    counts = ProposalCounts()
    for index, item in enumerate(items, 1):
        truth = data.masks(item)
        height, width = truth.vegetation.shape
        records = predict(data.image(item))["regions"][:PROPOSAL_LIMIT]
        proposals = [proposal_mask(row, size=(width, height), kind="sam3") for row in records]
        instances = [
            instance_mask(instance, (height, width))
            for instance in data.instances.get(item.source_id, [])
        ]
        score_proposals(counts, truth, proposals, instances)
        _progress("SAM3 proposal scoring", len(items), index)
    return counts.metrics()


def run_proposals(context: RunContext) -> CheckResult:
    with dataset(context, proposals=True) as data:
        items = _selected(data, context, ("held-out",))
        metrics = _score_images(data, items, sam_predictor(context))
        release_cuda()
        return CheckResult(
            check=PROPOSALS,
            stage="region-proposals",
            dataset=DATASET,
            split="held-out",
            metrics=metrics,
            inputs=data.inputs | model_inputs(presence=False),
            configuration={
                **_configuration(context),
                "held_out_images": len(items),
                "proposal_budget": PROPOSAL_LIMIT,
                "proposal_order": (
                    "SAM3 retained order, prompt order then descending score per prompt"
                ),
                "component_connectivity": 8,
                "region_iou_threshold": REGION_THRESHOLD,
                "region_coverage_threshold": REGION_THRESHOLD,
                "nonvegetation_proposal_threshold": BACKGROUND_THRESHOLD,
            },
            limits=[
                *COMMON_LIMITS,
                "Connected vegetation pixels can merge several plants or split a single plant. "
                "Non-crowd potted plant polygon instances are scored separately.",
                "IoU and coverage use the best single proposal per truth region, ignoring void "
                "outside the truth. The same proposal can recover more than one region.",
                "The non-vegetation diagnostic counts labelled background over each whole "
                "proposal, including void in its denominator. It is a lower bound on background "
                "proposals and does not measure proposal precision.",
                "Wilson intervals treat pixels, regions or proposals as independent; their "
                "spatial and image-level dependence makes these intervals optimistic.",
            ],
        )


register(
    Check(PRESENCE, "plant-presence", DATASET, run_presence, "Vegetation recall by image share")
)
register(
    Check(PROPOSALS, "region-proposals", DATASET, run_proposals, "Vegetation mask proposal recall")
)
