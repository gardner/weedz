"Real PlantCLEF views/aggregation and a separate released XP4 feature-head control."

import gc
import importlib
import json
import logging
import sqlite3
import time
from collections.abc import Callable, Sequence
from contextlib import closing
from importlib.metadata import PackageNotFoundError, version
from itertools import batched
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from pydantic import BaseModel, ConfigDict, Field

from weedz.classification import plantclef
from weedz.discovery.inference import region_boxes, square_view
from weedz.species_aggregation import RankedTaxon, aggregate_taxa
from weedz.validation.fingerprint import imported_sources, pipeline_fingerprint
from weedz.validation.registry import RunContext
from weedz.validation.roadside_data import (
    DATASET,
    GROUPS,
    SPECIES,
    fetch_verified,
    sha256,
    source_pins,
)

BUDGET = 5
BATCH_SIZE = 4
GRID = 4
POLICY = "max_score"
LIBRARIES = ("torch", "torchvision", "timm", "pillow", "numpy", "scipy", "pydantic", "safetensors")
PLANT_WEIGHTS = Path(f"{DATASET}/models/plantclef/plantclef2024.safetensors")
PLANT_MAPPING = Path(f"{DATASET}/models/plantclef/species_id_mapping.txt")
XP4_WEIGHTS = Path(f"{DATASET}/models/model_tiling_state_dict_xp4.pth")
logger = logging.getLogger(__name__)


class Prediction(BaseModel):
    model_config = ConfigDict(frozen=True)
    methods: dict[str, tuple[str, ...]]
    inference_seconds: float = Field(default=0.0, ge=0, allow_inf_nan=False)


def library_versions() -> dict[str, str]:
    result = {}
    for package in LIBRARIES:
        try:
            distribution = version(package)
            module = importlib.import_module("PIL" if package == "pillow" else package)
            # CUDA overlays can shadow CPU wheels without shadowing their dist-info.
            result[package + "_version"] = str(getattr(module, "__version__", distribution))
        except (ImportError, PackageNotFoundError):
            result[package + "_version"] = "not installed"
    return result


def suggestions(crops: Sequence[Sequence[RankedTaxon]], budget: int = BUDGET) -> tuple[str, ...]:
    # Max-score is unchanged by singleton crops. Alphabetical encounter order
    # matches the production tile profile's tie-break before the budget is spent.
    alternatives = sorted((row for crop in crops for row in crop), key=lambda row: row.taxon)
    return tuple(aggregate_taxa([[row] for row in alternatives], policy=POLICY, budget=budget))


def publisher_suggestions(scores: tuple[float, ...], cutoffs: tuple[float, ...]) -> tuple[str, ...]:
    if len(scores) != len(GROUPS) or len(cutoffs) != len(GROUPS):
        raise ValueError("XP4 output must cover all six publisher groups")
    if not all(np.isfinite(value) and 0 <= value <= 1 for value in (*scores, *cutoffs)):
        raise ValueError("Invalid XP4 score/cutoff")
    return tuple(
        group
        for group, score, cutoff in zip(GROUPS, scores, cutoffs, strict=True)
        if score > cutoff
    )


def thresholds(root: Path) -> tuple[float, ...]:
    released = json.loads((root / DATASET / "metadata/xp4-thresholds.json").read_text())["xp4_val"]
    if set(released) != set(GROUPS):
        raise ValueError("Released XP4 threshold classes disagree")
    return tuple(float(np.float32(released[group])) for group in GROUPS)


def verify_models(context: RunContext, baseline: bool) -> dict[str, str]:
    if baseline:
        pin = source_pins()["models/model_tiling_state_dict_xp4.pth"]
        fetch_verified(
            context.data_root / XP4_WEIGHTS, pin["url"], pin["sha256"], context.cache_dir / DATASET
        )
        expected = {XP4_WEIGHTS: pin["sha256"]}
    else:
        expected = {PLANT_WEIGHTS: plantclef.WEIGHTS_SHA256, PLANT_MAPPING: plantclef.LABELS_SHA256}
    for path, digest in expected.items():
        if sha256(context.data_root / path) != digest:
            raise ValueError(f"Roadside checkpoint checksum mismatch: {path.name}")
    return {path.as_posix(): digest for path, digest in expected.items()}


def evidence_identity(context: RunContext, baseline: bool) -> str:
    return pipeline_fingerprint(
        imported_sources(Path("validation/roadside.py")),
        LIBRARIES,
        library_versions(),
        baseline,
        context.device,
        BUDGET,
        BATCH_SIZE,
        GRID,
        POLICY,
        SPECIES,
        source_pins()["models/model_tiling_state_dict_xp4.pth"]
        if baseline
        else (plantclef.WEIGHTS_SHA256, plantclef.LABELS_SHA256),
        thresholds(context.data_root) if baseline else "production overlap plus historical grid",
    )


def _grid_boxes(image: Image.Image) -> list[tuple[int, int, int, int]]:
    width, height = image.size
    return [
        (x * width // GRID, y * height // GRID, (x + 1) * width // GRID, (y + 1) * height // GRID)
        for y in range(GRID)
        for x in range(GRID)
    ]


def _ranks(logits: np.ndarray, labels: tuple[str, ...]) -> list[list[RankedTaxon]]:
    return [
        [
            RankedTaxon(taxon=row["taxon"], score=row["score"], score_kind=plantclef.SCORE_KIND)
            for row in plantclef.ranked_species(logit, labels, BUDGET)
        ]
        for logit in logits
    ]


def _group_ranking(shares: np.ndarray, indices: list[list[int]]) -> tuple[str, ...]:
    values = [float(shares[:, group].max()) for group in indices]
    return tuple(
        aggregate_taxa(
            [
                [
                    RankedTaxon(taxon=group, score=value, score_kind=plantclef.SCORE_KIND)
                    for group, value in zip(GROUPS, values, strict=True)
                ]
            ],
            policy=POLICY,
            budget=6,
        )
    )


def _load_plant(context: RunContext) -> Callable[[Path], Prediction]:
    model = plantclef.PlantClassifier.load(
        context.data_root / PLANT_WEIGHTS, context.data_root / PLANT_MAPPING, context.device
    )
    selected = tuple(model.labels.index(name) for group in SPECIES for name in group)
    group_indices: list[list[int]] = []
    offset = 0
    for group in SPECIES:
        group_indices.append(list(range(offset, offset + len(group))))
        offset += len(group)

    def predict(path: Path) -> Prediction:
        started = time.monotonic()
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        production = region_boxes(*image.size)
        # The original frame profile uses timm's unpadded centre crop. Tiles use square_view.
        views = [
            image,
            *(square_view(image, box) for box in production),
            *(square_view(image, box) for box in _grid_boxes(image)),
        ]
        outputs = [
            model.predict_selected(list(batch), selected) for batch in batched(views, BATCH_SIZE)
        ]
        logits = np.concatenate([output[0] for output in outputs])
        shares = np.concatenate([output[1] for output in outputs])
        ranks = _ranks(logits, model.labels)
        grid_start = 1 + len(production)
        whole_groups = _group_ranking(shares[1:2], group_indices)
        grid_groups = _group_ranking(shares[grid_start:], group_indices)
        return Prediction(
            methods={
                "frame_top5": suggestions(ranks[:1]),
                "tiles_top5": suggestions(ranks[1:grid_start]),
                "grid_top5": suggestions(ranks[grid_start:]),
                "six_group_whole_top1": whole_groups[:1],
                "six_group_whole_top3": whole_groups[:3],
                "six_group_grid_top1": grid_groups[:1],
                "six_group_grid_top3": grid_groups[:3],
            },
            inference_seconds=round(time.monotonic() - started, 6),
        )

    return predict


def _load_publisher(context: RunContext) -> Callable[[Path], Prediction]:
    import torch

    state = torch.load(context.data_root / XP4_WEIGHTS, weights_only=True, map_location="cpu")
    head = torch.nn.Linear(768, 6, device=context.device).eval()
    head.load_state_dict(
        {key.removeprefix("linear_classif."): value for key, value in state.items()}
    )
    cutoffs = thresholds(context.data_root)

    def predict(path: Path) -> Prediction:
        started = time.monotonic()
        features = torch.load(path, weights_only=True, map_location="cpu")
        if features.shape != (926, 768) or not features.isfinite().all():
            raise ValueError("Invalid publisher BEiT feature tensor")
        with torch.inference_mode():
            if context.device == "cuda:0":
                with torch.autocast("cuda", dtype=torch.float16):
                    values = head(features.float().to(context.device)).amax(dim=0).sigmoid().float()
            else:
                values = head(features.float()).amax(dim=0).sigmoid()
        scores = tuple(float(value) for value in values.cpu().tolist())
        ranking = tuple(GROUPS[i] for i in sorted(range(6), key=lambda i: -scores[i]))
        return Prediction(
            methods={
                "released_cutoffs": publisher_suggestions(scores, cutoffs),
                "six_group_top1": ranking[:1],
                "six_group_top3": ranking[:3],
            },
            inference_seconds=round(time.monotonic() - started, 6),
        )

    return predict


def load_predictor(context: RunContext, baseline: bool) -> Callable[[Path], Prediction]:
    import torch

    torch.set_num_threads(4)
    return _load_publisher(context) if baseline else _load_plant(context)


def predict_paths(context: RunContext, paths: list[Path], *, baseline: bool) -> list[Prediction]:
    "Verify checkpoints even on cache-only replay; commit evidence after every image."
    if context.device not in {"cpu", "cuda:0"}:
        raise ValueError("Roadside checks support cpu or cuda:0 only")
    verify_models(context, baseline)
    identity = evidence_identity(context, baseline)
    cache = context.cache_dir / DATASET
    cache.mkdir(parents=True, exist_ok=True)
    predictor: Callable[[Path], Prediction] | None = None
    result = []
    started = time.monotonic()
    try:
        with closing(sqlite3.connect(cache / "predictions.sqlite3", timeout=60)) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS evidence (identity TEXT, source TEXT, value TEXT, "
                "PRIMARY KEY(identity, source))"
            )
            for index, path in enumerate(paths, 1):
                key = identity, sha256(path)
                row = db.execute(
                    "SELECT value FROM evidence WHERE identity=? AND source=?", key
                ).fetchone()
                if row is None:
                    predictor = predictor or load_predictor(context, baseline)
                    evidence = predictor(path)
                    with db:
                        db.execute(
                            "INSERT INTO evidence VALUES (?, ?, ?)",
                            (*key, evidence.model_dump_json()),
                        )
                else:
                    evidence = Prediction.model_validate_json(row[0])
                result.append(evidence)
                if index % 50 == 0 or index == len(paths):
                    logger.info(
                        "Roadside %s %d/%d (%.1fs)",
                        "XP4" if baseline else "PlantCLEF",
                        index,
                        len(paths),
                        time.monotonic() - started,
                    )
    finally:
        predictor = None
        gc.collect()
        if context.device == "cuda:0":
            import torch

            torch.cuda.empty_cache()
    return result
