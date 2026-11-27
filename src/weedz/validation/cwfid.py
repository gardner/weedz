"""CWFID sparse crop/weed positives on the publisher test split, excluding overlap."""

import logging
from collections.abc import Callable
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from weedz.labelled.archive import SourceArchive
from weedz.labelled.cwfid import ARCHIVE_SHA256, REVISION
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

NAME = "cwfid-mask-coverage"
ARCHIVE = Download(f"https://codeload.github.com/cwfid/dataset/tar.gz/{REVISION}", ARCHIVE_SHA256)
logger = logging.getLogger(__name__)


def test_ids(split: dict[str, list[int]]) -> list[str]:
    return [f"{number:03}" for number in sorted(set(split["test"]) - set(split["train"]))]


def development_ids(split: dict[str, list[int]]) -> list[str]:
    return [f"{number:03}" for number in sorted(set(split["train"]) - set(split["test"]))]


def positive_masks(colours: np.ndarray) -> dict[str, BoolMask]:
    if colours.ndim != 3 or colours.shape[2] != 3:
        raise ValueError("CWFID annotations must have RGB colours")
    crop = np.all(colours == (0, 255, 0), axis=2)
    weed = np.all(colours == (255, 0, 0), axis=2)
    black = np.all(colours == 0, axis=2)
    if not (crop | weed | black).all():
        raise ValueError("Unknown CWFID annotation colour")
    return {"crop": crop, "weed": weed, "assessed": crop | weed}


def load_items(
    context: RunContext, development: bool = False
) -> tuple[list[tuple[str, Path, Path]], dict[str, str]]:
    relative = Path("cwfid/source") / f"cwfid-{REVISION}.tar.gz"
    path = verified_download(ARCHIVE, context.data_root / relative)
    inputs = {str(relative): ARCHIVE.sha256}
    result = []
    with SourceArchive(path, ARCHIVE.sha256) as source:
        prefix = f"dataset-{REVISION}"
        raw = source.read(f"{prefix}/train_test_split.yaml")
        materialize(context.data_root, Path("cwfid/train_test_split.yaml"), raw, inputs)
        ids = development_ids if development else test_ids
        for name in select(ids(yaml.safe_load(raw)), context.limit):
            image = materialize(
                context.data_root,
                Path(f"cwfid/images/{name}.png"),
                source.read(f"{prefix}/images/{name}_image.png"),
                inputs,
            )
            annotation = materialize(
                context.data_root,
                Path(f"cwfid/annotations/{name}.png"),
                source.read(f"{prefix}/annotations/{name}_annotation.png"),
                inputs,
            )
            result.append((name, image, annotation))
    return result, inputs


def run(context: RunContext, predict: Callable[[Path], list[dict]] | None = None) -> CheckResult:
    items, inputs = load_items(context)
    development, development_inputs = load_items(context, development=True)
    inputs.update(development_inputs)
    inputs.update(model_inputs(context.data_root))
    predict = predict or sam_predictor(context, "cwfid")
    tally = Tallies()
    dev_tally = Tallies()
    proposals = 0
    for index, (_, image, annotation) in enumerate(items + development, 1):
        counts = tally if index <= len(items) else dev_tally
        with Image.open(annotation) as source:
            truth = positive_masks(np.asarray(source.convert("RGB")))
        shape = truth["assessed"].shape
        records = predict(image)
        if index <= len(items):
            proposals += len(records)
        masks = [proposal_mask(row, size=(shape[1], shape[0]), kind="sam3") for row in records]
        union = mask_union(masks, shape)
        for category, mask in truth.items():
            image_coverage(counts, mask, union, "all" if category == "assessed" else category)
        logger.info("CWFID %d/%d", index, len(items) + len(development))
    del predict
    release_cuda()
    config = configuration(context)
    config["cohort_sha256"] = cohort_sha256(
        [(name, "held-out") for name, *_ in items]
        + [(name, "development") for name, *_ in development]
    )
    config["gate_split_policy"] = (
        "publisher train development; publisher test held-out; exclude 028"
    )
    config["gate_development_images"] = len(development)
    limits: list[str] = []
    metrics = apply_development_gates(
        tally.metrics(),
        dev_tally.metrics(),
        ("foreground_90pct_covered",),
        config,
        limits,
    )
    metrics.extend(prefixed(dev_tally.metrics(), "development"))
    return CheckResult(
        check=NAME,
        stage="region-proposals",
        dataset="CWFID publisher test, no overlap",
        split="test",
        metrics=metrics,
        inputs=inputs,
        configuration={
            **config,
            **sam_configuration(),
            **tally.means(),
            "images": len(items),
            "proposals": proposals,
            "proposal_budget": "all retained (128 per prompt)",
            "excluded_overlap_id": "028",
            "split_rule": "publisher test minus train",
        },
        limits=[
            *limits,
            "Already inspected during development. The publisher test split is preserved, "
            "but this is not independent held-out evidence. Source image 028 is in both "
            "train and test and is excluded.",
            "Only red weed and green crop pixels are assessed positives. Black pixels are "
            "unlabelled, never absent. No precision, false alarms or species identity is measured.",
            "Sparse human plant/part polygons were intersected with the publisher NDVI/Otsu "
            "vegetation mask. Algorithmic boundaries are not dense human ground truth.",
            "Coverage is computed per positive image/category; Wilson trials are images, "
            "not spatially dependent pixels. Category masks with no positive pixels are skipped.",
            "False-colour Red/Near-Infrared/Red imagery; natural-RGB transfer is limited. "
            "Noncommercial research only. Pretraining overlap remains unknown.",
            "Historical CWFID results used SAM2 and all 60 photos; this check uses default SAM3 "
            "and 20 nonoverlapping publisher test photos, so the headline is not comparable.",
        ],
    )


register(
    Check(
        NAME,
        "region-proposals",
        "CWFID",
        run,
        "Image-level coverage of sparse assessed crop/weed positive pixels",
    )
)
