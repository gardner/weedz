"""PlantCLEF 2024 publisher val/test subjects, scored with the frozen iNat machinery."""

import json
import os
from collections import Counter, defaultdict
from dataclasses import replace
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from weedz.validation.fingerprint import imported_sources, pipeline_fingerprint
from weedz.validation.inat2021 import (
    Predictor,
    Scored,
    _configuration,
    score_false_alarms,
    score_species,
)
from weedz.validation.inat2021_data import TARGETS, Item, subject_stratum
from weedz.validation.inat2021_models import Prediction, predict_all, verify_inputs
from weedz.validation.inat2021_overlap import TRAINING_URL
from weedz.validation.metrics import Rate
from weedz.validation.plantclef2024_data import (
    DOWNLOAD_DELAY,
    DOWNLOAD_WORKERS,
    IMAGE_BASE,
    LABELS_PATH,
    LABELS_SHA256,
    OTHER_BUDGET,
    SAMPLE_SALT,
    Photo,
    labels_file,
    load_photos,
    prepare_images,
    select_photos,
)
from weedz.validation.registry import Check, RunContext, register
from weedz.validation.scorecard import CheckResult

SPECIES_ID = "plantclef2024-target-species"
FALSE_ALARMS = "plantclef2024-target-false-alarms"
DATASET = "PlantCLEF 2024 single-plant publisher val/test"
STAGES = {SPECIES_ID: "species-identification", FALSE_ALARMS: "target-false-alarms"}
LIBRARIES = (
    "torch",
    "torchvision",
    "timm",
    "pillow",
    "numpy",
    "open_clip_torch",
    "safetensors",
    "pydantic",
)
LIMITS = (
    "Labels identify the photographed subject, not every plant in the frame. A different "
    "labelled subject supports a wrong-subject target suggestion, never scene-level absence.",
    "Publisher learn_tag train photos are excluded. The organisers used val for model selection; "
    "test is the cleanest estimate of PlantCLEF generalization. DINOv2 pretraining image overlap "
    "and BioCLIP 2 TreeOfLife-200M overlap are not audited.",
    "Clematis paniculata, Austroderia, Leptospermum, Kunzea, Clematis forsteri and "
    "Clematis foetida are absent. Cytisus scoparius is a lookalike, not a watchlist target.",
    "Only 20 val/test photos per target species. Wilson intervals use photos as units; photos "
    "may share observations and are not guaranteed independent. This southwestern European "
    "single-plant cohort does not estimate New Zealand scene performance or prevalence.",
    "Organ tags are reported descriptively for target photos, not as reliable botanical strata.",
    "Non-targets include every available same-genus/same-family subject and a salted-hash sample "
    "of 5,000 other plants. The pooled rate depends on this deliberately enriched cohort. "
    "BioCLIP rankings cover only the frozen watchlist/comparison prompt vocabulary.",
    "Per-photo licences and authors are retained in metadata and image receipts; licences vary. "
    "Images stay outside Git. The converted PlantCLEF checkpoint is CC BY-NC 4.0.",
    "The publisher provides no per-image checksums. First HTTPS downloads establish local "
    "SHA-256 receipts; every replay verifies those bytes. The metadata and model assets are "
    "verified against pinned SHA-256 checksums even on an entirely cached run.",
)


def library_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for library in LIBRARIES:
        try:
            versions[f"{library}_version"] = version(library)
        except PackageNotFoundError:
            versions[f"{library}_version"] = "not installed"
    return versions


def evidence_identity(device: str) -> str:
    return pipeline_fingerprint(
        imported_sources(Path("validation/plantclef2024.py")),
        LIBRARIES,
        device,
        _configuration(),
    )


def _metrics(photos: list[Photo], rows: Scored, *, targets: bool) -> list[Rate]:
    score = score_species if targets else score_false_alarms
    metrics = score(rows)
    for tag in ("val", "test"):
        members = [
            row for photo, row in zip(photos, rows, strict=True) if photo.publisher_split == tag
        ]
        for metric in score(members):
            stratum = tag if metric.stratum == "all" else f"{tag}/{metric.stratum}"
            metrics.append(metric.model_copy(update={"stratum": stratum}))
    return metrics


def _configuration_for(
    photos: list[Photo], context: RunContext
) -> dict[str, str | int | float | bool]:
    # Retain the exact shared rule settings while replacing iNat-specific dataset fields.
    config = {
        key: value
        for key, value in _configuration().items()
        if not key.startswith(("labels_archive", "images_archive", "held_out_fraction"))
    }
    organs: dict[str, dict[str, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    for photo in photos:
        if photo.item.taxon in TARGETS:
            organs[photo.item.taxon][photo.publisher_split][photo.organ] += 1
    counts = Counter(f"{p.publisher_split}/{subject_stratum(p.item)}" for p in photos)
    config.update(
        {
            "publisher_split": "val + test; no dataset tuning",
            "metadata_url": TRAINING_URL,
            "image_backup_url_base": IMAGE_BASE,
            "other_plants_budget": OTHER_BUDGET,
            "other_plants_sampling": "lowest SHA-256(salt:source_id), pooled across val/test",
            "other_plants_sample_salt": SAMPLE_SALT,
            "device": context.device,
            "download_workers": DOWNLOAD_WORKERS,
            "download_delay_seconds": DOWNLOAD_DELAY,
            "target_organ_counts": json.dumps(organs, sort_keys=True),
            "scored_cohort_counts": json.dumps(counts, sort_keys=True),
            "sample_limit_applied": context.limit is not None,
            "scored_subjects": len(photos),
            "evidence_identity": evidence_identity(context.device),
        }
    )
    config.update(library_versions())
    return config


def run_check(
    check: str,
    context: RunContext,
    photos: list[Photo],
    predictor: Predictor,
    *,
    inputs: dict[str, str] | None = None,
) -> CheckResult:
    if context.limit is not None and context.limit < 1:
        raise ValueError("PlantCLEF smoke limit must be positive")
    targets = check == SPECIES_ID
    selected = select_photos(photos, targets=targets)[: context.limit]
    items = [photo.item for photo in selected]
    rows = list(zip(items, predictor(items), strict=True))
    return CheckResult(
        check=check,
        stage=STAGES[check],
        dataset=DATASET,
        split="validation",
        metrics=_metrics(selected, rows, targets=targets),
        inputs=inputs or {},
        configuration=_configuration_for(selected, context),
        limits=list(LIMITS),
    )


def _run(check: str, context: RunContext) -> CheckResult:
    path = labels_file(context.data_root)
    # Verify all six assets before consulting any prediction cache.
    inputs = {str(LABELS_PATH): LABELS_SHA256, **verify_inputs(context.data_root)}
    photos = load_photos(path)
    by_id = {photo.item.source_id: photo for photo in photos}
    cache = context.cache_dir / "plantclef2024"
    evidence_cache = cache / evidence_identity(context.device)
    evidence_cache.mkdir(parents=True, exist_ok=True)

    def predictor(items: list[Item]) -> list[Prediction]:
        selected = [by_id[item.source_id] for item in items]
        inputs["plantclef2024/scored images (SHA-256 of per-file digests)"] = prepare_images(
            cache, selected
        )
        # predict_all locates photos below data_root/inat2021. Adapt only that path;
        # shared inference, model paths, cue decisions and its existing cache keys stay intact.
        adapted = [
            replace(
                item,
                file_name=os.path.relpath(cache / item.file_name, context.data_root / "inat2021"),
            )
            for item in items
        ]
        return predict_all(context, evidence_cache, adapted)

    return run_check(check, context, photos, predictor, inputs=inputs)


register(Check(SPECIES_ID, STAGES[SPECIES_ID], DATASET, lambda ctx: _run(SPECIES_ID, ctx)))
register(Check(FALSE_ALARMS, STAGES[FALSE_ALARMS], DATASET, lambda ctx: _run(FALSE_ALARMS, ctx)))
