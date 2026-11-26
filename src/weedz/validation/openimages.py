"""Open Images V7 checks using Weedz intake and regional proposals."""

import hashlib
import json
import logging
import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from importlib.metadata import version
from pathlib import Path
from typing import Any, Literal

import httpx
from PIL import Image

from weedz.discovery.vegetation import MODEL_FILES, VegetationScreener, vegetation_fraction
from weedz.region_evaluation.boxes import Box, box_iou
from weedz.region_evaluation.matching import match_regions
from weedz.segmentation.sam3_image import CHECKPOINT_SHA256, CODE_REVISION, Sam3Config, Sam3Image
from weedz.validation.fingerprint import SAM3_SOURCES, SEGFORMER_SOURCES, pipeline_fingerprint
from weedz.validation.metrics import Outcome, Rate, binary_metrics, rate
from weedz.validation.openimages_data import (
    BOXES,
    CLASSES,
    DATASET_DIR,
    HIERARCHY,
    IMAGE_BYTE_LIMIT,
    LABELS,
    NEGATIVE_BUDGET,
    POSITIVE_BUDGET,
    SIZES,
    SMALL_MINIMUM,
    Item,
    image_path,
    load_items,
    rows,
    select_items,
    sha256,
    size_stratum,
    vegetation_scope,
    verify_metadata,
    write_atomic,
)
from weedz.validation.registry import Check, RunContext, register
from weedz.validation.scorecard import CheckResult
from weedz.validation.splits import SALT

logger = logging.getLogger(__name__)

DATASET = "Open Images V7 validation"
PRESENCE = "openimages-plant-presence"
BOX_RECALL = "openimages-plant-boxes"
RECALL_TARGET = 0.95
FALSE_ALARM_CEILING = 0.10
PROPOSAL_BUDGET = 100
IOU_THRESHOLD = 0.5
PROPOSAL_PROMPTS = Sam3Config().prompts
SAM_CONFIG = Sam3Config(prompts=(*PROPOSAL_PROMPTS, "tree", "grass", "shrub"))
MODEL_DIR = Path(DATASET_DIR, "models")
SAM_CHECKPOINT = MODEL_DIR / "sam3.pt"
SEG_SNAPSHOT = MODEL_DIR / "segformer"
type ModelName = Literal["sam3", "segformer"]
PIPELINE_SOURCES: dict[ModelName, tuple[Path, ...]] = {
    "sam3": SAM3_SOURCES,
    "segformer": SEGFORMER_SOURCES,
}
COMMON_LIMITS = [
    "Plant and its boxable subclasses define scope. Verification and exhaustiveness apply to "
    "publisher classes, and may miss other vegetation such as grass or shrubs.",
    "CVDF JPEGs retain the stored camera orientation used for the authored boxes.",
    "Open Images annotations are CC BY 4.0. Image listings are CC BY 2.0 without warranty.",
    "This cohort measures performance on Open Images, with transfer to NZ field photos unmeasured.",
]
PRESENCE_LIMITS = [
    "The 11,851 Plant rows with decimal confidence are positive and negative combined. "
    "There are 7,081 verified Plant-absent rows, with 7,000 eligible after conflicts. "
    "The publisher's official class hierarchy supports inference downwards from a verified Plant "
    "absence. A positive descendant or any vegetation box overrides eligibility as a negative. "
    "Missing labels and negative descendant labels alone do not establish Plant absence.",
    "The largest individual non-depiction vegetation box sets positive size. Group-of boxes "
    "can cover gaps between plants, so they do not set size. Verified positives with no usable "
    "boxes remain in the cohort.",
    "Overall recall is for the sampled cohort with small photos oversampled. The current "
    "SegFormer ranker orders all scores and has no rejection threshold.",
    "Only 202 held-out and 231 development positives qualify as small. Full runs include all.",
]
BOX_LIMITS = [
    "The proposal denominator includes individual non-depiction vegetation boxes in sampled "
    "held-out positives. Group-of boxes have ambiguous extent and are excluded.",
    "Unmatched proposals can cover other, unboxed plants. "
    "This check measures proposal recall only.",
    "Box Wilson intervals describe the pooled boxes and do not adjust for image-level clustering.",
]


def recall_threshold(development_positive_scores: Sequence[float]) -> float:
    """Highest inclusive threshold recovering at least 95% of development positives."""
    if not development_positive_scores:
        raise ValueError("Threshold selection requires development positives")
    ordered = sorted(development_positive_scores, reverse=True)
    return ordered[math.ceil(RECALL_TARGET * len(ordered)) - 1]


def presence_metrics(
    items: Sequence[Item], scores: Mapping[str, float], threshold: float, method: str
) -> list[Rate]:
    outcomes = (
        Outcome(
            item=item.id,
            truth=item.present,
            predicted=scores[item.id] >= threshold,
            stratum=item.stratum,
        )
        for item in items
    )
    return [
        metric.model_copy(update={"name": f"{method}_{metric.name}"})
        for metric in binary_metrics(
            outcomes, target_recall=RECALL_TARGET, false_alarm_ceiling=FALSE_ALARM_CEILING
        )
    ]


def box_metrics(items: Sequence[Item], predict: Callable[[Item], Sequence[Box]]) -> list[Rate]:
    totals: Counter[str] = Counter()
    hits: Counter[str] = Counter()
    for item in items:
        truth = [label for label in item.boxes if not label.group]
        if not truth:
            continue
        proposals = predict(item)[:PROPOSAL_BUDGET]
        overlaps = [[box_iou(label.box, proposal) for proposal in proposals] for label in truth]
        matching = match_regions(overlaps, threshold=IOU_THRESHOLD, proposal_count=len(proposals))
        for label in truth:
            totals[size_stratum(label.area)] += 1
        for pair in matching.matches:
            hits[size_stratum(truth[pair.truth].area)] += 1
    return [
        rate("sam3_box_recall", hits.total(), totals.total()),
        *[rate("sam3_box_recall", hits[size], totals[size], stratum=size) for size in SIZES],
    ]


@dataclass(frozen=True)
class SamPrediction:
    score: float
    boxes: list[Box]


def _normalized_box(raw: Sequence[float], width: int, height: int) -> Box:
    left, top, right, bottom = raw
    return left / width, top / height, right / width, bottom / height


def _sam_prediction(model: Sam3Image, path: Path) -> SamPrediction:
    # SAM3 boxes are in the EXIF-upright frame and Open Images boxes in the stored one.
    # No sampled CVDF JPEG has a rotation tag; refuse one rather than mis-score its boxes.
    with Image.open(path) as image:
        width, height = image.size
        orientation = image.getexif().get(0x0112, 1)
    if orientation != 1:
        raise ValueError(f"{path.name} has EXIF orientation {orientation}; boxes would not align")
    result = model.screen(path)
    if result["failed_prompts"]:
        errors = [
            (prompt["prompt"], prompt.get("failure_type"))
            for prompt in result["prompts"]
            if prompt["status"] == "failed"
        ]
        raise RuntimeError(f"SAM3 failed on {path.name}: {errors}")
    top_scores = [
        score
        for prompt in result["prompts"]
        for score in prompt["raw_top_concept_scores_before_retention"][:1]
    ]
    retained = [region for region in result["regions"] if region["prompt"] in PROPOSAL_PROMPTS]
    boxes = [_normalized_box(region["box"], width, height) for region in retained[:PROPOSAL_BUDGET]]
    return SamPrediction(max(top_scores, default=0.0), boxes)


def _seg_prediction(model: VegetationScreener, path: Path) -> float:
    with Image.open(path) as image:
        return vegetation_fraction(model.predict(image))


def _load_sam(context: RunContext, cache: Path) -> Callable[[Path], SamPrediction]:
    model = Sam3Image.load(
        context.data_root / SAM_CHECKPOINT,
        SAM_CONFIG,
        cache,
        max_source_bytes=IMAGE_BYTE_LIMIT,
    )
    return lambda path: _sam_prediction(model, path)


def _load_seg(context: RunContext) -> Callable[[Path], float]:
    model = VegetationScreener.load(context.data_root / SEG_SNAPSHOT, context.device)
    return lambda path: _seg_prediction(model, path)


def _profile(context: RunContext, method: ModelName) -> str:
    settings = (
        (CHECKPOINT_SHA256, CODE_REVISION, asdict(SAM_CONFIG), PROPOSAL_PROMPTS, PROPOSAL_BUDGET)
        if method == "sam3"
        else (MODEL_FILES,)
    )
    packages = ("torch", "numpy", "pillow", *(() if method == "sam3" else ("transformers",)))
    fingerprint = pipeline_fingerprint(
        PIPELINE_SOURCES[method], packages, 1, context.device, settings
    )
    return f"{method}-{fingerprint}"


def _predict_all[T](
    items: Sequence[Item],
    images: Mapping[str, Path],
    output: Path,
    load: Callable[[], Callable[[Path], T]],
    encode: Callable[[T], Any],
    decode: Callable[[Any], T],
) -> dict[str, T]:
    predict = None
    results = {}
    for index, item in enumerate(items, 1):
        path = images[item.id]
        digest = path.with_suffix(".sha256").read_text().strip()
        receipt = output / f"{item.id}-{digest}.json"
        if receipt.exists():
            prediction = decode(json.loads(receipt.read_text()))
        else:
            if predict is None:
                predict = load()
            prediction = predict(path)
            write_atomic(receipt, json.dumps(encode(prediction), allow_nan=False).encode())
        results[item.id] = prediction
        if index % 100 == 0 or index == len(items):
            logger.info("%s processed %d/%d images", output.name, index, len(items))
    return results


def _sam_from_json(raw: dict[str, Any]) -> SamPrediction:
    boxes = [_normalized_box(box, 1, 1) for box in raw["boxes"]]
    return SamPrediction(float(raw["score"]), boxes)


def _images(items: Sequence[Item], cache: Path) -> dict[str, Path]:
    ids = [item.id for item in items]
    logger.info("Preparing %d Open Images JPEGs", len(ids))
    limits = httpx.Limits(max_connections=16, max_keepalive_connections=16)
    with (
        httpx.Client(timeout=30, limits=limits, headers={"Accept-Encoding": "identity"}) as client,
        ThreadPoolExecutor(max_workers=16) as executor,
    ):
        paths = executor.map(lambda item_id: image_path(cache, item_id, client), ids)
        return dict(zip(ids, paths, strict=True))


def _cohort_digest(images: Mapping[str, Path]) -> str:
    manifest = "\n".join(
        f"{item_id} {path.with_suffix('.sha256').read_text().strip()}"
        for item_id, path in images.items()
    )
    return hashlib.sha256(manifest.encode()).hexdigest()


def _metadata(context: RunContext) -> tuple[dict[str, str], list[Item], dict[str, str]]:
    inputs = verify_metadata(context.data_root)
    metadata = context.data_root / DATASET_DIR / "metadata"
    names = {row["LabelName"]: row["DisplayName"] for row in rows(metadata / CLASSES)}
    plant = next(label for label, name in names.items() if name == "Plant")
    scope = vegetation_scope(metadata / HIERARCHY, plant)
    items = load_items(metadata / LABELS, metadata / BOXES, plant, scope)
    return inputs, items, {label: names[label] for label in sorted(scope)}


def _checkpoints(root: Path, *, segformer: bool) -> dict[str, str]:
    expected = {SAM_CHECKPOINT: CHECKPOINT_SHA256}
    if segformer:
        expected.update(
            {SEG_SNAPSHOT / filename: digest for filename, digest in MODEL_FILES.items()}
        )
    for path, digest in expected.items():
        if sha256(root / path) != digest:
            raise ValueError(f"Open Images model checksum mismatch for {path}")
    return {path.as_posix(): digest for path, digest in expected.items()}


def _configuration(
    scope: dict[str, str], context: RunContext
) -> dict[str, str | int | float | bool]:
    return {
        "device": context.device,
        "split_salt": SALT,
        "vegetation_classes": json.dumps(scope, sort_keys=True),
        "negative_policy": "verified Plant absent, with no positive descendant or vegetation box",
        "positive_budget_per_split": POSITIVE_BUDGET,
        "negative_budget_per_split": NEGATIVE_BUDGET,
        "small_minimum_per_split": SMALL_MINIMUM,
        "sam3_prompts": ", ".join(SAM_CONFIG.prompts),
        "sam3_max_side": SAM_CONFIG.max_side,
        "sam3_max_regions_per_prompt": SAM_CONFIG.max_regions,
        "sam3_max_bytes_per_prompt": SAM_CONFIG.max_prompt_bytes,
        "sam3_min_mask_pixels": SAM_CONFIG.min_area,
        "sam3_processor_resolution": 1008,
        "sam3_processor_threshold": 0.0,
        "sam3_retention_threshold": SAM_CONFIG.concept_threshold,
        "sam3_source_byte_budget": IMAGE_BYTE_LIMIT,
        "smoke_limit": context.limit or 0,
        "torch": version("torch"),
        "numpy": version("numpy"),
        "pillow": version("pillow"),
        "sam3_code_revision": CODE_REVISION,
    }


def _validate_context(context: RunContext, *, minimum: int) -> None:
    if context.device != "cuda:0":
        raise ValueError("The pinned Weedz SAM3 pipeline requires --device cuda:0")
    if context.limit is not None and context.limit < minimum:
        raise ValueError(f"Open Images smoke runs require --limit >= {minimum}")


def _sam_all(
    items: Sequence[Item], images: Mapping[str, Path], context: RunContext, cache: Path
) -> dict[str, SamPrediction]:
    profile = cache / _profile(context, "sam3")
    return _predict_all(
        items,
        images,
        profile,
        lambda: _load_sam(context, profile / "pipeline"),
        asdict,
        _sam_from_json,
    )


def run_presence(context: RunContext) -> CheckResult:
    _validate_context(context, minimum=2)
    inputs, items, scope = _metadata(context)
    inputs.update(_checkpoints(context.data_root, segformer=True))
    development = select_items(items, "development", limit=context.limit)
    held_out = select_items(items, "held-out", limit=context.limit)
    cohort = development + held_out
    cache = context.cache_dir / DATASET_DIR
    images = _images(cohort, cache)
    segmented = _predict_all(
        cohort,
        images,
        cache / _profile(context, "segformer"),
        lambda: _load_seg(context),
        float,
        float,
    )
    # The SegFormer callable has been released before SAM3 allocates GPU memory.
    from torch import cuda

    cuda.empty_cache()
    sam = _sam_all(cohort, images, context, cache)
    configuration = _configuration(scope, context)
    configuration.update(
        cohort_images_sha256=_cohort_digest(images),
        development_images=len(development),
        held_out_images=len(held_out),
        sam3_presence_score="maximum raw concept score across the five prompts",
        segformer_presence_score="vegetation fraction of the ADE20K argmax grid",
        segformer_ranker_policy="rank all scores; no rejection threshold",
        transformers=version("transformers"),
        threshold_rule="highest inclusive threshold reaching 95% development recall",
    )
    metrics = []
    for method, scores in (
        ("segformer", segmented),
        ("sam3", {key: value.score for key, value in sam.items()}),
    ):
        threshold = recall_threshold([scores[item.id] for item in development if item.present])
        configuration[f"{method}_threshold"] = threshold
        metrics.extend(presence_metrics(held_out, scores, threshold, method))
    return CheckResult(
        check=PRESENCE,
        stage="plant-presence",
        dataset=DATASET,
        split="held-out",
        metrics=metrics,
        limits=COMMON_LIMITS + PRESENCE_LIMITS,
        inputs=inputs,
        configuration=configuration,
    )


def run_boxes(context: RunContext) -> CheckResult:
    _validate_context(context, minimum=1)
    inputs, items, scope = _metadata(context)
    inputs.update(_checkpoints(context.data_root, segformer=False))
    positives = [
        item for item in select_items(items, "held-out", negative_budget=0) if item.present
    ][: context.limit]
    boxed = [item for item in positives if any(not label.group for label in item.boxes)]
    cache = context.cache_dir / DATASET_DIR
    images = _images(boxed, cache)
    predictions = _sam_all(boxed, images, context, cache)
    configuration = _configuration(scope, context)
    configuration.update(
        cohort_images_sha256=_cohort_digest(images),
        proposal_budget=PROPOSAL_BUDGET,
        proposal_prompts=", ".join(PROPOSAL_PROMPTS),
        proposal_order="plant then flower, descending score within each prompt",
        iou_threshold=IOU_THRESHOLD,
        held_out_positives=len(positives),
        positives_with_individual_boxes=len(boxed),
        group_of_boxes_excluded=sum(label.group for item in positives for label in item.boxes),
    )
    return CheckResult(
        check=BOX_RECALL,
        stage="region-proposals",
        dataset=DATASET,
        split="held-out",
        metrics=box_metrics(boxed, lambda item: predictions[item.id].boxes),
        limits=COMMON_LIMITS + BOX_LIMITS,
        inputs=inputs,
        configuration=configuration,
    )


register(Check(PRESENCE, "plant-presence", DATASET, run_presence))
register(Check(BOX_RECALL, "region-proposals", DATASET, run_boxes))
