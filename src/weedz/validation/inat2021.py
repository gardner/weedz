"""Species identification and wrong-subject target suggestions on iNat2021 validation."""

import json
from collections import defaultdict
from collections.abc import Callable
from itertools import chain

from weedz.discovery.inference import LABELS, MODELS, prompt
from weedz.discovery.lookalikes import LOOKALIKES
from weedz.validation.inat2021_data import (
    IMAGES_ARCHIVE_MD5,
    LABELS_ARCHIVE_MD5,
    LABELS_PATH,
    LABELS_SHA256,
    NEGATIVE_STRATA,
    SOURCE,
    TARGETS,
    Item,
    labels_file,
    load_items,
    prepare_images,
    subject_stratum,
)
from weedz.validation.inat2021_models import (
    BATCH_SIZE,
    GRID,
    LOCAL_FLOOR,
    LOCAL_MARGIN,
    PILOT_FLOOR,
    TOP_K,
    Prediction,
    predict_all,
    verify_inputs,
)
from weedz.validation.inat2021_overlap import TRAINING_URL, audit_overlap
from weedz.validation.metrics import Rate, rate
from weedz.validation.registry import Check, RunContext, register
from weedz.validation.scorecard import CheckResult
from weedz.validation.splits import SALT

SPECIES_ID = "inat2021-target-species"
FALSE_ALARMS = "inat2021-target-false-alarms"
DATASET = "iNat2021 validation"
STAGES = {SPECIES_ID: "species-identification", FALSE_ALARMS: "target-false-alarms"}
CUE_CEILING = 0.01
WORST_SPECIES = 15
Predictor = Callable[[list[Item]], list[Prediction]]
Scored = list[tuple[Item, Prediction]]
Flag = Callable[[Item, Prediction], bool]

LIMITS = (
    "The publisher labels the photographed subject. A different labelled subject establishes "
    "that a watchlist suggestion is wrong for that subject, while the rest of the frame is "
    "unannotated. These rates do not establish scene-level target absence or false alarms.",
    "The pipeline watchlist is Clematis vitalba, Cortaderia selloana and Ulex europaeus. "
    "Cytisus scoparius is a declared lookalike. Cortaderia jubata is same genus, and "
    "Cytisus proliferus, Genista species and Leptospermum laevigatum are outside the "
    "declared lookalike set. Austroderia richardii qualifies via the genus-level declaration.",
    "iNat2021 validation lacks Kunzea, Austroderia fulvida, Austroderia toetoe, "
    "Clematis forsteri and Clematis foetida.",
    "There are ten publisher validation photos per species before the source-ID split. "
    "Held-out per-species estimates are small, and the species-balanced cohort does not "
    "represent deployment prevalence or the composition of New Zealand scenes.",
    "BioCLIP 2 TreeOfLife-200M includes GBIF images from iNaturalist. Undetected overlap may "
    "make these estimates optimistic. PlantCLEF uses mostly Pl@ntNet with a GBIF supplement.",
    "The benchmark covers target identification and suggestions. Species outside the fixed "
    "BioCLIP prompt vocabulary cannot be identified by that classifier.",
    "Publisher terms allow non-commercial research and education. "
    "Images must not be redistributed.",
)

RECALL: dict[str, Flag] = {
    "plantclef_top1_recall": lambda i, p: i.taxon in p.plantclef[:1],
    "plantclef_top5_recall": lambda i, p: i.taxon in p.plantclef[:TOP_K],
    "bioclip_top1_recall": lambda i, p: i.taxon in p.bioclip[:1],
    "bioclip_top5_recall": lambda i, p: i.taxon in p.bioclip[:TOP_K],
    "pilot_cue_recall": lambda i, p: i.taxon == p.pilot_cue,
    "local_cue_recall": lambda i, p: i.taxon == p.local_cue,
}
SUGGESTIONS: dict[str, Callable[[Prediction], str | None]] = {
    "plantclef_top1": lambda p: next(iter(p.plantclef), None),
    "bioclip_top1": lambda p: next(iter(p.bioclip), None),
    "pilot_cue": lambda p: p.pilot_cue,
    "local_cue": lambda p: p.local_cue,
}


def _rate(name: str, stratum: str, rows: Scored, hit: Flag, ceiling: float | None = None) -> Rate:
    return rate(
        name,
        sum(hit(item, pred) for item, pred in rows),
        len(rows),
        stratum=stratum,
        ceiling=ceiling,
    )


def _by_species(rows: Scored) -> dict[str, Scored]:
    groups: dict[str, Scored] = defaultdict(list)
    for item, prediction in rows:
        groups[item.taxon].append((item, prediction))
    return groups


def score_species(rows: Scored) -> list[Rate]:
    positive = [(item, pred) for item, pred in rows if subject_stratum(item) == "target"]
    lookalikes = [(item, pred) for item, pred in rows if subject_stratum(item) == "lookalike"]
    positives = _by_species(positive)
    metrics = [
        _rate(name, group, members, hit)
        for group, members in [
            ("all", positive),
            *((taxon, positives.get(taxon, [])) for taxon in TARGETS),
        ]
        for name, hit in RECALL.items()
    ]
    negative_groups = [("all", lookalikes), *sorted(_by_species(lookalikes).items())]
    for name, suggest in SUGGESTIONS.items():
        for group, members in negative_groups:
            hits = sum(suggest(pred) in TARGETS for _, pred in members)
            metrics.append(rate(f"{name}_confusion", hits, len(members), stratum=group))
    return metrics


def _false_alarm_rates(
    name: str, suggest: Callable[[Prediction], str | None], rows: Scored
) -> list[Rate]:
    groups: dict[str, Scored] = defaultdict(list)
    for item, pred in rows:
        groups[subject_stratum(item)].append((item, pred))

    def hit(_item: Item, pred: Prediction) -> bool:
        return suggest(pred) in TARGETS

    ceiling = CUE_CEILING if name.endswith("_cue") else None
    metrics = [_rate(f"{name}_wrong_subject", "all", rows, hit, ceiling)]
    metrics.extend(
        _rate(f"{name}_wrong_subject", group, groups[group], hit) for group in NEGATIVE_STRATA
    )
    worst = [
        _rate(f"{name}_worst_species", taxon, members, hit)
        for taxon, members in _by_species(rows).items()
    ]
    metrics.extend(
        sorted((m for m in worst if m.successes), key=lambda m: (-m.successes, m.stratum))[
            :WORST_SPECIES
        ]
    )
    return metrics


def score_false_alarms(rows: Scored) -> list[Rate]:
    negatives = [(item, pred) for item, pred in rows if subject_stratum(item) != "target"]
    return list(
        chain.from_iterable(
            _false_alarm_rates(name, suggest, negatives) for name, suggest in SUGGESTIONS.items()
        )
    )


def _eligible(check: str, item: Item) -> bool:
    stratum = subject_stratum(item)
    return stratum != "target" if check == FALSE_ALARMS else stratum in {"target", "lookalike"}


def _configuration() -> dict[str, str | int | float | bool]:
    return {
        "publisher_split": "validation",
        "split_salt": SALT,
        "held_out_fraction": 0.5,
        "targets": json.dumps(TARGETS),
        "lookalikes": json.dumps(sorted(row["name"] for row in LOOKALIKES.values())),
        "labels_archive_url": f"{SOURCE}/val.json.tar.gz",
        "labels_archive_md5": LABELS_ARCHIVE_MD5,
        "images_archive_url": f"{SOURCE}/val.tar.gz",
        "images_archive_md5": IMAGES_ARCHIVE_MD5,
        "plantclef_training_metadata_url": TRAINING_URL,
        "plantclef_rank": "full 7,806 classes, whole photo, letterboxed, binomial comparison",
        "bioclip_rank": "whole photo, letterboxed, raw cosine over all fixed prompts",
        "bioclip_revision": MODELS["bioclip-2"]["revision"],
        "bioclip_prompts": json.dumps([prompt(label) for label in LABELS]),
        "top_k": TOP_K,
        "batch_size": BATCH_SIZE,
        "grid_side": GRID,
        "plantclef_views": GRID * GRID + 1,
        "bioclip_views": 2,
        "cue_budget_per_rule": 1,
        "pilot_tile_floor": PILOT_FLOOR,
        "pilot_agreement": "winning tile, whole-frame watchlist winner, native EfficientNet top 1",
        "local_tile_floor": LOCAL_FLOOR,
        "local_bioclip_margin": LOCAL_MARGIN,
        "local_agreement": "winning PlantCLEF tile and best BioCLIP target on the same crop",
        "wrong_subject_cue_ceiling": CUE_CEILING,
        "worst_species_budget_per_method": WORST_SPECIES,
    }


def run_check(
    check: str,
    context: RunContext,
    items: list[Item],
    predictor: Predictor,
    *,
    inputs: dict[str, str] | None = None,
    extra_limits: tuple[str, ...] = (),
) -> CheckResult:
    # Every rule here is frozen and nothing is tuned on iNat2021, so both halves are unseen.
    selected = [item for item in items if _eligible(check, item)]
    selected = selected[: context.limit]
    rows = list(zip(selected, predictor(selected), strict=True))
    metrics = score_species(rows) if check == SPECIES_ID else score_false_alarms(rows)
    config = _configuration()
    config["device"] = context.device
    config["sample_limit_applied"] = context.limit is not None
    config["scored_subjects"] = len(selected)
    return CheckResult(
        check=check,
        stage=STAGES[check],
        dataset=DATASET,
        split="validation",
        metrics=metrics,
        inputs=inputs or {},
        configuration=config,
        limits=[*LIMITS, *extra_limits],
    )


def _run(check: str, context: RunContext) -> CheckResult:
    if context.limit is not None and context.limit < 1:
        raise ValueError("iNat2021 smoke limit must be positive")
    root = context.data_root
    cache = context.cache_dir / "inat2021"
    labels = load_items(labels_file(root, cache))
    overlap_inputs, overlap_limit = audit_overlap(root, labels)
    inputs = {str(LABELS_PATH): LABELS_SHA256, **verify_inputs(root), **overlap_inputs}

    def predictor(items: list[Item]) -> list[Prediction]:
        prepare_images(root, cache, items)
        return predict_all(context, cache, items)

    return run_check(
        check, context, labels, predictor, inputs=inputs, extra_limits=(overlap_limit,)
    )


register(Check(SPECIES_ID, STAGES[SPECIES_ID], DATASET, lambda ctx: _run(SPECIES_ID, ctx)))
register(Check(FALSE_ALARMS, STAGES[FALSE_ALARMS], DATASET, lambda ctx: _run(FALSE_ALARMS, ctx)))
