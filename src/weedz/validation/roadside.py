"""Whole-photo labelled-positive recovery on Danish publisher test and multilabel scenes.

The problem: the previous roadside numbers depended on private, bounded scripts.
This adapter freezes public inputs and calls the production classifier and aggregation.
A six-group diagnostic preserves the older question without restricting the main list.
"""

import json
from collections.abc import Callable

from weedz.discovery.inference import LETTERBOX, MAX_STRIDE, MAX_TILES, TILE_FRACTION
from weedz.discovery.lookalikes import LOOKALIKES
from weedz.discovery.records import SPECIES as WATCHLIST
from weedz.validation.gates import apply_development_gates, cohort_sha256
from weedz.validation.metrics import Rate, rate
from weedz.validation.registry import Check, RunContext, register
from weedz.validation.roadside_data import (
    DATASET,
    DISTANCE_METRES,
    GROUPS,
    Item,
    acquire_assets,
    groups_for,
    load_items,
    prepare_metadata,
    read_membership,
)
from weedz.validation.roadside_models import (
    BATCH_SIZE,
    BUDGET,
    GRID,
    POLICY,
    Prediction,
    evidence_identity,
    library_versions,
    predict_paths,
    thresholds,
    verify_models,
)
from weedz.validation.scorecard import CheckResult
from weedz.validation.splits import SALT

SPECIES = "danish-roadside-species"
BASELINE = "danish-roadside-publisher-baseline"
STAGE = "whole-photo-species"
Predictor = Callable[[list[Item]], list[Prediction]]
COHORTS = ("all", "test", "test/distance-filtered", "multilabel", "multilabel/distance-filtered")
LOOKALIKE_NAMES = {row["name"] for row in LOOKALIKES.values()}
LIMITS = [
    (
        "Only explicit human-positive image-group pairs are scored. Blank CSV cells "
        "and the no-species folder are not used as negatives; annotation "
        "exhaustiveness is unverified. No precision or false-alarm claim."
    ),
    (
        "The 206 multilabel photos are separate from the publisher's 2,140-photo test "
        "split; they are reported separately and pooled, never relabelled as test "
        "photos."
    ),
    (
        "Filename-coordinate proximity crosses publisher splits. The "
        "distance-filtered stratum is >100 m from train, validation and the other "
        "scoring cohort. Scored neighbours are not mutually separated; dates/routes "
        "still overlap and independent sites are unverified."
    ),
    (
        "Wilson intervals treat labelled pairs as independent; route proximity and "
        "multiple labels in one photo can make these intervals optimistic."
    ),
    (
        "Danish groups are not a New Zealand scene answer key. Only Cytisus scoparius "
        "is a labelled pipeline lookalike; no watchlist target is labelled (reported "
        "unmeasured). Unlabelled incidental taxa remain unassessed."
    ),
    (
        "The publisher does not supply per-file SHA-256 hashes for original "
        "JPEGs/features. The checked-in manifest pins HTTPS-acquired bytes; it is not "
        "an independently signed publisher manifest."
    ),
    (
        "Dataset and XP4 release: CC BY 4.0 (Zenodo API records 14013930/13891416); "
        "publisher code: MIT. The reused PlantCLEF checkpoint is CC BY-NC 4.0. "
        "Images and checkpoints stay outside Git."
    ),
]


def _cohorts(item: Item) -> tuple[str, ...]:
    base = ("all", item.source_split)
    return (*base, f"{item.source_split}/distance-filtered") if item.distance_filtered else base


def _groups(group: str) -> tuple[str, ...]:
    names = ("all", group)
    if group in WATCHLIST:
        return (*names, "watchlist")
    return (*names, "lookalikes") if group in LOOKALIKE_NAMES else names


def _stratum(cohort: str, group: str) -> str:
    return "all" if (cohort, group) == ("all", "all") else f"{cohort}/{group}"


def score(pairs: list[tuple[Item, Prediction]]) -> list[Rate]:
    if len({item.source_id for item, _ in pairs}) != len(pairs):
        raise ValueError("Each roadside photo may be scored once")
    methods = list(pairs[0][1].methods) if pairs else []
    counts = {
        (method, cohort, group): [0, 0]
        for method in methods
        for cohort in COHORTS
        for group in ("all", *GROUPS, "watchlist", "lookalikes")
    }
    for item, prediction in pairs:
        if set(prediction.methods) != set(methods):
            raise ValueError("Roadside prediction methods disagree")
        for method, names in prediction.methods.items():
            recovered = groups_for(names)
            for positive in item.positives:
                for cohort in _cohorts(item):
                    for group in _groups(positive):
                        count = counts.setdefault((method, cohort, group), [0, 0])
                        count[0] += positive in recovered
                        count[1] += 1
    return [
        rate(f"{method}_recall", hits, total, stratum=_stratum(cohort, group))
        for (method, cohort, group), (hits, total) in counts.items()
    ]


def selected_items(items: list[Item], limit: int | None) -> list[Item]:
    if limit is not None and limit < 1:
        raise ValueError("Roadside smoke limit must be positive")
    # Stable source IDs, rather than directory order or labels, define the smoke prefix.
    return sorted(
        (item for item in items if item.split == "held-out" and item.source_split != "val"),
        key=lambda item: item.source_id,
    )[:limit]


def gate_items(items: list[Item], source_split: str, limit: int | None) -> list[Item]:
    """Publisher val/test positives supply the regression trials; blanks add no trials."""
    return sorted(
        (item for item in items if item.source_split == source_split and item.positives),
        key=lambda item: item.source_id,
    )[:limit]


def inference_items(items: list[Item], limit: int | None) -> list[Item]:
    combined = [
        *selected_items(items, limit),
        *gate_items(items, "val", limit),
        *gate_items(items, "test", limit),
    ]
    return list({item.source_id: item for item in combined}.values())


def publisher_metrics(pairs: list[tuple[Item, Prediction]]) -> list[Rate]:
    metrics = []
    for source, split in (("val", "development"), ("test", "held-out")):
        for metric in score([row for row in pairs if row[0].source_split == source]):
            if metric.stratum == "all" or metric.stratum.startswith("all/"):
                suffix = "" if metric.stratum == "all" else metric.stratum.removeprefix("all")
                metrics.append(metric.model_copy(update={"stratum": split + suffix}))
    return metrics


def _model_configuration(baseline: bool) -> dict[str, str | int | float | bool]:
    if baseline:
        return {
            "model": "released XP4 linear/max/sigmoid head over supplied BEiT features",
            "class_count": 6,
            "feature_views": 926,
            "feature_dimensions": 768,
            "suggestion_budget": "variable (six strict released cutoffs)",
            "aggregation": "maximum logit over 926 feature rows then sigmoid",
            "precision": "released CUDA FP16 autocast; CPU fallback FP32",
            "prompts": "none (six publisher groups)",
            "tuning": "none; frozen published validation cutoffs",
            "comparison": "released XP4 thresholds from publisher validation only",
        }
    return {
        "model": "PlantCLEF2024 DINOv2 ViT-B/14 reg4 fully fine-tuned",
        "class_count": 7806,
        "suggestion_budget": BUDGET,
        "aggregation": POLICY,
        "per_view_alternatives": BUDGET,
        "production_views": (
            "unmodified frame control; tiles = square_view over region_boxes (includes "
            "padded whole frame)"
        ),
        "tile_fraction": TILE_FRACTION,
        "max_stride": MAX_STRIDE,
        "max_tiles": MAX_TILES,
        "letterbox_rgb": json.dumps(LETTERBOX),
        "historical_grid": GRID,
        "historical_padding": "Pillow ImageOps.pad rounded centering (earlier grid)",
        "precision": "FP32; production fp32_math policy",
        "classifier_batch": BATCH_SIZE,
        "production_vocabulary": "all 7,806 PlantCLEF classes",
        "prompts": "none (PlantCLEF full closed vocabulary)",
        "tuning": "no dataset tuning; frozen production budget/geometry and historical 4x4 control",
        "comparison": (
            "six_group_* diagnostics rank only six Danish groups, unlike the "
            "full-vocabulary five-slot main list"
        ),
    }


def _configuration(
    check: str, context: RunContext, items: list[Item]
) -> dict[str, str | int | float | bool]:
    return {
        **library_versions(),
        **_model_configuration(check == BASELINE),
        "limit": context.limit or "none",
        "images": len(items),
        "test_images": sum(item.source_split == "test" for item in items),
        "multilabel_images": sum(item.source_split == "multilabel" for item in items),
        "distance_filtered_images": sum(item.distance_filtered for item in items),
        "device": context.device,
        "split_salt": SALT,
        "source_id": "publisher JPEG filename",
        "split_policy": (
            "split_of(source_id); held-out only within publisher test and separate multilabel"
        ),
        "distance_filter_metres": DISTANCE_METRES,
        "distance_filter": (
            "3D Earth chord from filename coordinates; >100m from train+val+other scoring cohort"
        ),
        "scored_pairs": sum(len(item.positives) for item in items),
        "photos_without_positive_label": sum(not item.positives for item in items),
    }


def run_check(
    check: str,
    context: RunContext,
    items: list[Item],
    predictor: Predictor,
    *,
    inputs: dict[str, str] | None = None,
) -> CheckResult:
    selected = selected_items(items, context.limit)
    cohort = inference_items(items, context.limit)
    evidence = predictor(cohort)
    by_id = dict(zip((item.source_id for item in cohort), evidence, strict=True))
    predictions = [by_id[item.source_id] for item in selected]
    configuration = _configuration(check, context, selected)
    configuration["recorded_inference_seconds"] = round(
        sum(prediction.inference_seconds for prediction in predictions), 3
    )
    configuration["inference_timing_scope"] = (
        "per-photo decode/load plus every reported inference method; excludes model initialization"
    )
    for method in predictions[0].methods if predictions else ():
        suggestions = sum(len(prediction.methods[method]) for prediction in predictions)
        configuration[f"{method}_total_suggestions"] = suggestions
    limits = list(LIMITS)
    configuration["cohort_sha256"] = cohort_sha256(
        (i.source_id, f"{i.source_split}/{'|'.join(i.positives)}") for i in cohort
    )
    metrics = score(list(zip(selected, predictions, strict=True)))
    metrics.extend(publisher_metrics(list(zip(cohort, evidence, strict=True))))
    metrics = apply_development_gates(
        metrics,
        metrics,
        ("released_cutoffs_recall",) if check == BASELINE else ("tiles_top5_recall",),
        configuration,
        limits,
        development_stratum="development",
        held_out_stratum="held-out",
    )
    configuration["gate_split_policy"] = (
        "publisher val positives development; all publisher test positives held-out"
    )
    configuration["gate_development_images"] = len(gate_items(items, "val", context.limit))
    configuration["gate_held_out_images"] = len(gate_items(items, "test", context.limit))
    configuration["gate_recorded_inference_seconds"] = round(
        sum(p.inference_seconds for p in evidence), 3
    )
    limits.append(
        "Regression gates use labelled publisher val/test folder positives. Legacy "
        "hash-selected test plus multilabel rows are retained ungated. No route split "
        "was needed; neighbouring publisher val/test frames still limit independence."
    )
    if check == BASELINE:
        limits.append(
            "XP4 comparison scores the released linear/max/sigmoid head over cached "
            "publisher BEiT features (926 views), not end-to-end feature extraction. "
            "Released strict cutoffs select a variable number of groups; this is not a "
            "five-slot comparison."
        )
    else:
        limits.append(
            "The earlier 16/21 top-one result used 25 distance-screened reserve frames "
            "and a six-group 4x4 ranking. This larger hash-held-out cohort and the "
            "full-vocabulary production list ask different questions; the six_group_grid "
            "rows preserve its ranking method."
        )
    return CheckResult(
        check=check,
        stage=STAGE,
        dataset=DATASET,
        split="held-out",
        metrics=metrics,
        limits=limits,
        inputs=inputs or {},
        configuration=configuration,
    )


def run(context: RunContext, *, baseline: bool = False) -> CheckResult:
    if context.device not in {"cpu", "cuda:0"}:
        raise ValueError("Roadside checks support cpu or cuda:0 only")
    staging = context.cache_dir / DATASET / "downloads"
    inputs = prepare_metadata(context.data_root, staging)
    items = load_items(
        context.data_root / DATASET / "metadata/multilabel.csv",
        read_membership(context.data_root),
        include_development=True,
    )
    selected = inference_items(items, context.limit)
    paths, assets = acquire_assets(context.data_root, staging, selected, baseline=baseline)
    inputs.update(assets)
    inputs.update(verify_models(context, baseline))
    predictions = predict_paths(context, paths, baseline=baseline)
    result = run_check(
        BASELINE if baseline else SPECIES, context, items, lambda _: predictions, inputs=inputs
    )
    config = dict(result.configuration)
    config["evidence_identity"] = evidence_identity(context, baseline)
    if baseline:
        config["suggestion_budget"] = "variable (six strict released cutoffs)"
        for group, cutoff in zip(GROUPS, thresholds(context.data_root), strict=True):
            config[f"cutoff_{group}"] = cutoff
        config["publisher_revision"] = "043379010d0081eb23f58146bcdbf94f611b3f7f"
        config["cutoff_comparison"] = "strict score > released threshold (float32)"
        config["calibration_split"] = "publisher validation (2160 photos), no test fitting"
        config["calibration_rule"] = "released xp4_val; maximum Youden J on publisher validation"
    return result.model_copy(update={"configuration": config})


register(
    Check(
        SPECIES,
        STAGE,
        DATASET,
        run,
        "Positive-pair recovery in broad five-slot PlantCLEF scene suggestions",
    )
)
register(
    Check(
        BASELINE,
        STAGE,
        DATASET,
        lambda context: run(context, baseline=True),
        "Released XP4 head and fixed validation cutoffs on publisher features",
    )
)
