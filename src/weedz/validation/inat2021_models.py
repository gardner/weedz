"""Raw model evidence and the two frozen review decisions."""

import hashlib
import io
import json
import logging
import sqlite3
from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import dataclass
from importlib.metadata import version
from itertools import batched
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

from weedz.classification import aotearoa, plantclef
from weedz.classification.bioclip import BioClipClassifier
from weedz.discovery.encoder_backend import PROFILE
from weedz.discovery.inference import (
    COMPARISONS,
    LABELS,
    LETTERBOX,
    MODELS,
    Screener,
    file_sha256,
    summarize_scores,
)
from weedz.species_aggregation import RankedTaxon, aggregate_taxa
from weedz.validation.inat2021_data import TARGETS, Item
from weedz.validation.registry import RunContext

PILOT_FLOOR = 0.13646656274795532
LOCAL_FLOOR = 0.01173484418541193
LOCAL_MARGIN = 0.02411
GRID = 4
TOP_K = 5
BATCH_SIZE = 16
PLANT_LABELS = {
    "Clematis vitalba": "Clematis vitalba L.",
    "Ulex europaeus": "Ulex europaeus L.",
    "Cortaderia selloana": "Cortaderia selloana (Schult. & Schult.f.) Asch. & Graebn.",
}
MODEL_PATH = Path("inat2021/models")
PLANT_WEIGHTS = MODEL_PATH / "plantclef/plantclef2024.safetensors"
PLANT_MAPPING = MODEL_PATH / "plantclef/species_id_mapping.txt"
CLIP_CONFIG = MODEL_PATH / "bioclip2/open_clip_config.json"
CLIP_WEIGHTS = MODEL_PATH / "bioclip2" / MODELS["bioclip-2"]["weights"]
NATIVE_WEIGHTS = MODEL_PATH / "native/s.pth"
NATIVE_MAPPING = MODEL_PATH / "native/waikato-class-metadata.json"
MODEL_INPUTS = {
    PLANT_WEIGHTS: plantclef.WEIGHTS_SHA256,
    PLANT_MAPPING: plantclef.LABELS_SHA256,
    CLIP_CONFIG: "1bf947e96e943fe50efd5c3e26c37f843a2fa3c358967719a68c8a6d17ce68c8",
    CLIP_WEIGHTS: "b7b2bf6fbc95799e42630e394cf95803892ab447c1a8ab629dbc82fbeaf7dfef",
    NATIVE_WEIGHTS: "8916efcac8401a829f39a598a83a858c146c8ca2fa0ee92f9ddd6a2809ddf275",
    NATIVE_MAPPING: aotearoa.LABELS_SHA256,
}
logger = logging.getLogger(__name__)


class PlantEvidence(BaseModel):
    top: tuple[str, ...]
    whole_target: str
    tile_target: str
    tile_index: int = Field(ge=0, lt=GRID * GRID)
    tile_score: float = Field(ge=0, le=1)


class ClipEvidence(BaseModel):
    top: tuple[str, ...]
    tile_target: str
    tile_margin: float = Field(ge=-2, le=2)


class NativeEvidence(BaseModel):
    top: str


@dataclass(frozen=True)
class Prediction:
    plantclef: tuple[str, ...]
    bioclip: tuple[str, ...]
    pilot_cue: str | None
    local_cue: str | None


def decisions(
    plant: PlantEvidence, clip: ClipEvidence, native: str
) -> tuple[str | None, str | None]:
    target = plant.tile_target
    pilot = plant.tile_score >= PILOT_FLOOR and target == plant.whole_target == native
    local = (
        plant.tile_score >= LOCAL_FLOOR
        and target == clip.tile_target
        and clip.tile_margin >= LOCAL_MARGIN
    )
    return target if pilot else None, target if local else None


def _canonical(taxon: str) -> str:
    return " ".join(taxon.split()[:2])


def _grid_box(image: Image.Image, index: int) -> tuple[int, int, int, int]:
    y, x = divmod(index, GRID)
    w, h = image.size
    return x * w // GRID, y * h // GRID, (x + 1) * w // GRID, (y + 1) * h // GRID


def _all_views(image: Image.Image) -> Iterable[Image.Image]:
    for crop in (image, *(image.crop(_grid_box(image, i)) for i in range(GRID * GRID))):
        side = max(crop.size)
        yield ImageOps.pad(crop, (side, side), color=LETTERBOX)


def _plant_evidence(
    logits: np.ndarray, shares: np.ndarray, labels: tuple[str, ...]
) -> PlantEvidence:
    whole = tuple(PLANT_LABELS)[int(shares[0].argmax())]
    # The pilot breaks ties by watchlist order, then by row-major tile order.
    tiles = shares[1:]
    maxima = [
        RankedTaxon(taxon=target, score=float(score), score_kind=plantclef.SCORE_KIND)
        for target, score in zip(PLANT_LABELS, tiles.max(axis=0), strict=True)
    ]
    target = aggregate_taxa([maxima], policy="max_score", budget=1)[0]
    winner = tuple(PLANT_LABELS).index(target)
    tile = int(tiles[:, winner].argmax())
    ranking = plantclef.ranked_species(logits[0], labels, TOP_K)
    return PlantEvidence(
        top=tuple(_canonical(row["taxon"]) for row in ranking),
        whole_target=whole,
        tile_target=target,
        tile_index=tile,
        tile_score=float(tiles[tile, winner]),
    )


def verify_inputs(data_root: Path) -> dict[str, str]:
    for path, expected in MODEL_INPUTS.items():
        absolute = data_root / path
        if not absolute.is_file():
            raise FileNotFoundError(f"Link the existing model asset at {path} under --data-root")
        if file_sha256(absolute) != expected:
            raise ValueError(f"iNat2021 model asset SHA-256 mismatch: {path}")
    return {str(path): digest for path, digest in MODEL_INPUTS.items()}


def _open(encoded: bytes) -> Image.Image:
    with Image.open(io.BytesIO(encoded)) as source:
        return ImageOps.exif_transpose(source).convert("RGB")


@dataclass(frozen=True)
class ImageSource:
    path: Path
    sha256: str
    tile: int = 0

    def image(self) -> Image.Image:
        encoded = self.path.read_bytes()
        if hashlib.sha256(encoded).hexdigest() != self.sha256:
            raise ValueError(f"iNat2021 image changed while scoring: {self.path}")
        return _open(encoded)


def _plant_batch(
    model: plantclef.PlantClassifier, indices: tuple[int, ...], sources: list[ImageSource]
) -> list[PlantEvidence]:
    views = (view for source in sources for view in _all_views(source.image()))
    logits, shares = zip(
        *(model.predict_selected(list(batch), indices) for batch in batched(views, BATCH_SIZE)),
        strict=True,
    )
    # Cache only the whole-image ranking and the fixed grid's best target/tile evidence.
    size = GRID * GRID + 1
    return [
        _plant_evidence(np.asarray(lg), np.asarray(sh), model.labels)
        for lg, sh in zip(
            batched(np.concatenate(logits), size),
            batched(np.concatenate(shares), size),
            strict=True,
        )
    ]


def _load_plant(root: Path, device: str) -> Callable[[list[ImageSource]], list[PlantEvidence]]:
    model = plantclef.PlantClassifier.load(root / PLANT_WEIGHTS, root / PLANT_MAPPING, device)
    indices = tuple(model.labels.index(PLANT_LABELS[target]) for target in PLANT_LABELS)

    def predict(sources: list[ImageSource]) -> list[PlantEvidence]:
        return _plant_batch(model, indices, sources)

    return predict


def _clip_evidence(whole: np.ndarray, tile: np.ndarray) -> ClipEvidence:
    names = [*TARGETS, *COMPARISONS]
    top = tuple(names[i].split(",", 1)[0] for i in np.argsort(-whole, kind="stable")[:TOP_K])
    result = summarize_scores(tile[None], [(0, 0, 1, 1)], names, len(TARGETS))
    return ClipEvidence(top=top, tile_target=result["best_species"], tile_margin=result["margin"])


def _load_clip(root: Path, device: str) -> Callable[[list[ImageSource]], list[ClipEvidence]]:
    backend = PROFILE if device == "cuda:0" else "cpu"
    model = BioClipClassifier(
        Screener.load(model="bioclip-2", backend=backend, snapshot=(root / CLIP_CONFIG).parent)
    )

    def predict(sources: list[ImageSource]) -> list[ClipEvidence]:
        images = [source.image() for source in sources]
        tiles = [
            image.crop(_grid_box(image, source.tile))
            for source, image in zip(sources, images, strict=True)
        ]
        whole = model.view_similarities(images)
        local = model.view_similarities(tiles)
        return [_clip_evidence(a, b) for a, b in zip(whole, local, strict=True)]

    return predict


def _load_native(root: Path, device: str) -> Callable[[list[ImageSource]], list[NativeEvidence]]:
    import timm
    import torch

    labels = aotearoa.class_labels((root / NATIVE_MAPPING).read_bytes())
    model = timm.create_model(
        "tf_efficientnetv2_s.in21k", pretrained=False, num_classes=len(labels)
    )
    weights = torch.load(root / NATIVE_WEIGHTS, map_location="cpu", weights_only=True)
    model.load_state_dict(weights["model"], strict=True)
    model.to(device).float().eval()
    del weights

    def transform(image: Image.Image) -> torch.Tensor:
        return torch.from_numpy(aotearoa.preprocess(image)[0])

    classifier = plantclef.PlantClassifier(model, transform, labels, {"device": device})

    def predict(sources: list[ImageSource]) -> list[NativeEvidence]:
        rows = classifier.predict([source.image() for source in sources], top_k=1)
        return [NativeEvidence(top=row[0]["taxon"]) for row in rows]

    return predict


def _identity(stage: str, device: str) -> str:
    paths = {
        "plantclef": (PLANT_WEIGHTS, PLANT_MAPPING),
        "bioclip": (CLIP_WEIGHTS, CLIP_CONFIG),
        "native": (NATIVE_WEIGHTS, NATIVE_MAPPING),
    }
    specifications = {
        "plantclef": [GRID, LETTERBOX, TOP_K, PLANT_LABELS],
        "bioclip": [GRID, LETTERBOX, TOP_K, LABELS, MODELS["bioclip-2"]],
        "native": [aotearoa.INPUT_POLICY],
    }
    libraries = ("torch", "torchvision", "timm", "pillow", "numpy", "open_clip_torch")
    payload = [
        1,
        stage,
        device,
        BATCH_SIZE,
        [MODEL_INPUTS[p] for p in paths[stage]],
        specifications[stage],
        [version(name) for name in libraries],
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _cached_batches[Evidence: BaseModel](
    db: sqlite3.Connection,
    stage: str,
    context: RunContext,
    sources: list[ImageSource],
    evidence_type: type[Evidence],
    load: Callable[[Path, str], Callable[[list[ImageSource]], list[Evidence]]],
) -> list[Evidence]:
    identity = _identity(stage, context.device)
    predict = None
    result: list[Evidence] = []
    for batch in batched(sources, BATCH_SIZE):
        keys = [(identity, src.sha256, src.tile) for src in batch]
        rows = [
            db.execute(
                "SELECT evidence FROM predictions WHERE model=? AND image=? AND tile=?", key
            ).fetchone()
            for key in keys
        ]
        missing = [index for index, row in enumerate(rows) if row is None]
        if missing:
            if predict is None:
                predict = load(context.data_root, context.device)
            predictions = predict([batch[index] for index in missing])
            with db:
                for index, evidence in zip(missing, predictions, strict=True):
                    rows[index] = (evidence.model_dump_json(),)
                    db.execute(
                        "INSERT OR REPLACE INTO predictions VALUES (?, ?, ?, ?)",
                        (*keys[index], rows[index][0]),
                    )
        result.extend(evidence_type.model_validate_json(row[0]) for row in rows if row is not None)
        if len(result) % (BATCH_SIZE * 64) == 0 or len(result) == len(sources):
            logger.info("%s evidence %d/%d", stage, len(result), len(sources))
    return result


def _stage[Evidence: BaseModel](
    db: sqlite3.Connection,
    stage: str,
    context: RunContext,
    sources: list[ImageSource],
    evidence_type: type[Evidence],
    load: Callable[[Path, str], Callable[[list[ImageSource]], list[Evidence]]],
) -> list[Evidence]:
    import torch

    try:
        return _cached_batches(db, stage, context, sources, evidence_type, load)
    finally:
        if context.device == "cuda:0":
            torch.cuda.empty_cache()


def predict_all(context: RunContext, cache: Path, items: list[Item]) -> list[Prediction]:
    import torch

    if context.device not in {"cpu", "cuda:0"}:
        raise ValueError("iNat2021 supports cpu or cuda:0")
    torch.set_num_threads(4)
    paths = [context.data_root / "inat2021" / item.file_name for item in items]
    sources = [ImageSource(path, file_sha256(path)) for path in paths]
    with closing(sqlite3.connect(cache / "predictions.sqlite3", timeout=60)) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            "CREATE TABLE IF NOT EXISTS predictions (model TEXT, image TEXT, tile INTEGER, "
            "evidence TEXT NOT NULL, PRIMARY KEY(model, image, tile))"
        )
        plant = _stage(db, "plantclef", context, sources, PlantEvidence, _load_plant)
        tiles = [
            ImageSource(src.path, src.sha256, pl.tile_index)
            for src, pl in zip(sources, plant, strict=True)
        ]
        clip = _stage(db, "bioclip", context, tiles, ClipEvidence, _load_clip)
        native = _stage(db, "native", context, sources, NativeEvidence, _load_native)
    return [
        Prediction(pl.top, bc.top, *decisions(pl, bc, nz.top))
        for pl, bc, nz in zip(plant, clip, native, strict=True)
    ]
