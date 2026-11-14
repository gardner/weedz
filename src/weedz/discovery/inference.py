"""CPU BioCLIP screening of full frames plus overlapping regions, without training.

Scores are text/image cosine similarities. A tile is a search window, never a
segmentation mask or a localized plant boundary. No threshold is calibrated yet.
"""

import hashlib
import io
import json
import math
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
from PIL import Image, ImageOps

from weedz.discovery.records import SPECIES

# Bump when image decoding changes, so cached embeddings are not reused.
# Window geometry needs no bump: the exact boxes are part of the cache key.
WINDOW_REVISION = 2
# How window scores become a photo's margin and top suggestion; bump with any change, as
# score meanings (#16) and device reports (#57) are declared per ranking revision.
RANKING_REVISION = 4
# Declared, pinned screening models; a run records which one scored it (issue #14).
MODELS: dict[str, dict[str, str]] = {
    "bioclip": {
        "repo": "imageomics/bioclip",
        "revision": "ce901ab3c6a913f9e9ef94ce6d27761069f4f01c",
        "weights": "open_clip_pytorch_model.bin",
        "tokenizer": "ViT-B-16",
    },
    "bioclip-2": {
        "repo": "imageomics/bioclip-2",
        "revision": "2957b322090f9cb17ae72c71981c7218a28d81e0",
        "weights": "open_clip_model.safetensors",
        "tokenizer": "ViT-L-14",
    },
}
LOOKALIKES = [
    "Austroderia toetoe, New Zealand native toetoe grass",
    "Clematis paniculata, New Zealand native clematis vine",
    "Leptospermum scoparium, manuka shrub",
    "Cytisus scoparius, broom shrub",
    "mixed grass and native forest vegetation",
    "a bird",
    "a butterfly",
    "an insect",
    "a landscape with no visible plants",
]
# Backgrounds common in coastal animal photos that pale grasses otherwise "explain".
SCENES = [
    "open sky",
    "sea or open water",
    "sand, mud or a rocky shore",
    "bare rock",
]
COMPARISONS = LOOKALIKES + SCENES
# Every fixed label, watchlist targets first; a photo may add its own original subject.
LABELS = [f"{name}, {common}" for name, common in SPECIES.items()] + COMPARISONS


class Encoder(Protocol):
    def eval(self) -> Any: ...
    def encode_image(self, image: Any, *, normalize: bool) -> Any: ...
    def encode_text(self, text: Any, *, normalize: bool) -> Any: ...


TILE_FRACTION = 0.6
MAX_STRIDE = 0.75  # at least 25% overlap between neighbouring tiles
LETTERBOX = (124, 116, 104)  # neutral pad, close to the model's normalisation mean
# Greyscale standard deviation below which a tile has no visible structure. Pilot tiles
# showed a clear gap: a black night strip at 0.5, while 95% of tiles were above 12.
FEATURELESS_STD = 8.0
# Bounds for degenerate panoramas: tiles per photo, and windows per encoder batch.
MAX_TILES = 32
ENCODE_BATCH = 16


def _positions(length: int, side: int) -> list[int]:
    if length <= side:
        return [0]
    count = math.ceil((length - side) / (side * MAX_STRIDE)) + 1
    return [round(index * (length - side) / (count - 1)) for index in range(count)]


def _thin(positions: list[int], count: int) -> list[int]:
    step = (len(positions) - 1) / max(1, count - 1)
    return sorted({positions[round(index * step)] for index in range(count)})


def region_boxes(width: int, height: int) -> list[tuple[int, int, int, int]]:
    """The whole frame, then overlapping square tiles that together cover every pixel.

    Square tiles survive the model's centre-crop intact, so no edge strip is discarded.
    """
    side = max(1, round(min(width, height) * TILE_FRACTION))
    xs, ys = _positions(width, side), _positions(height, side)
    if len(xs) * len(ys) > MAX_TILES:
        # Degenerate panoramas: evenly thin the long axis; covers_every_pixel reports the gap.
        if width >= height:
            xs = _thin(xs, MAX_TILES // len(ys))
        else:
            ys = _thin(ys, MAX_TILES // len(xs))
    tiles = [(x, y, x + side, y + side) for y in ys for x in xs]
    return list(dict.fromkeys([(0, 0, width, height), *tiles]))


def covers_every_pixel(width: int, height: int) -> bool:
    """Whether the tiles alone (not the letterboxed frame) reach every pixel."""
    seen = np.zeros((height, width), bool)
    for x1, y1, x2, y2 in region_boxes(width, height)[1:]:
        seen[y1:y2, x1:x2] = True
    return bool(seen.all())


def square_view(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    """Crop a box and pad it to a square, so centre-cropping cannot remove any of it."""
    crop = image.crop(box)
    side = max(crop.size)
    if crop.size == (side, side):
        return crop
    canvas = Image.new("RGB", (side, side), LETTERBOX)
    canvas.paste(crop, ((side - crop.width) // 2, (side - crop.height) // 2))
    return canvas


def featureless(view: Image.Image) -> bool:
    """No visible structure (e.g. a black night strip), so no plant evidence to rank."""
    return float(np.asarray(view.convert("L"), dtype=float).std()) < FEATURELESS_STD


def summarize_scores(
    scores: np.ndarray,
    boxes: list[tuple[int, int, int, int]],
    labels: list[str],
    target_count: int,
    eligible: list[bool] | None = None,
) -> dict[str, Any]:
    """Best target-minus-comparison margin per species over the eligible windows."""
    allowed = np.array(eligible if eligible is not None else [True] * len(boxes))
    results = []
    for index, species in enumerate(labels[:target_count]):
        margins = scores[:, index] - np.max(scores[:, target_count:], axis=1)
        row = int(np.argmax(np.where(allowed, margins, -np.inf)))
        score = float(scores[row, index])
        margin = score - float(np.max(scores[row, target_count:]))
        results.append(
            {
                "name": species,
                "similarity": round(score, 6),
                "margin": round(margin, 6),
                "box": list(boxes[row]),
            }
        )
    best = max(results, key=lambda item: item["margin"])
    return {
        "best_species": best["name"],
        "similarity": best["similarity"],
        "margin": best["margin"],
        "box": best["box"],
        "species": results,
        "method": "BioCLIP cosine similarity; letterboxed frame + overlapping square tiles",
    }


def subject_label(photo: dict[str, Any]) -> str | None:
    """The photo's original subject, so a window showing it is not read as a weed.

    A watchlist target is never its own comparison: reference photos would score zero.
    That includes references identified below species, such as a gorse subspecies.
    """
    taxon = photo.get("original_taxon", "")
    # Reference and lookalike photos are measured against the watchlist; naming their own
    # taxon as a comparison would answer the question for the model.
    if photo.get("cohort") in {"reference", "lookalike"} or any(
        taxon == name or taxon.startswith(f"{name} ") for name in SPECIES
    ):
        return None
    names = [taxon, photo.get("original_common_name", "")]
    return ", ".join(name for name in names if name) or None


def prompt(label: str) -> str:
    return f"a photograph of {label}"


def file_sha256(path: Path) -> str:
    """Hash a large file in chunks rather than reading gigabytes of weights into memory."""
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def library_versions() -> dict[str, str]:
    """Versions of the code that decodes and resizes each window and computes its embedding.

    open_clip describes the transform, torchvision and Pillow carry it out, and torch runs
    the encoder, so upgrading any of them must invalidate cached embeddings and refuse
    mixed resumes.
    """
    import open_clip
    import PIL
    import torch
    import torchvision

    return {
        "open_clip": open_clip.__version__,
        "torch": torch.__version__,
        "torchvision": torchvision.__version__,
        "pillow": PIL.__version__,
    }


class Screener:
    def __init__(
        self,
        model: Encoder,
        transform: Any,
        tokenizer: Any,
        weights_sha256: str,
        cache_dir: Path | None = None,
        *,
        preprocessing: Mapping[str, Any],
        model_key: str = "bioclip",
    ) -> None:
        """`preprocessing` describes what `transform` does in stable, JSON-serialisable terms.

        It, not the transform object, keys the embedding cache: transform reprs can embed
        process-specific memory addresses, which would change the key on every restart.
        """
        import torch

        self.torch = torch
        self.model = model
        self.transform = transform
        self.tokenizer = tokenizer
        self.model.eval()
        self.labels = list(LABELS)
        self.prompts = [prompt(label) for label in self.labels]
        self.text = self.encode_text(self.prompts)
        self.cache_dir = cache_dir
        self.weights_sha256 = weights_sha256
        self.preprocessing_sha256 = hashlib.sha256(
            json.dumps(preprocessing, sort_keys=True).encode()
        ).hexdigest()
        self.metadata = {
            "model": MODELS[model_key]["repo"],
            "model_key": model_key,
            "revision": MODELS[model_key]["revision"],
            "weights_sha256": weights_sha256,
            "device": "cpu",
            "ranking_revision": RANKING_REVISION,
            "prompts": self.prompts,
            "subject_prompt": prompt("<original taxon>, <common name>"),
            "target_count": len(SPECIES),
            "regions": (
                "letterboxed whole image and overlapping square tiles covering every pixel, "
                f"except photos needing more than {MAX_TILES} tiles, whose long axis is thinned; "
                "each result's coverage_complete says which"
            ),
            "ranking": (
                "maximum target minus best comparison-label cosine similarity per window; "
                "comparisons include the photo's original subject; featureless tiles "
                f"(greyscale std < {FEATURELESS_STD:g}) cannot be the winning window"
            ),
            "calibrated": False,
            "segmentation": False,
            "embedding_cache": {
                "key": "sha256(image bytes, weights, preprocessing, window boxes, window revision)",
                "window_revision": WINDOW_REVISION,
                "preprocessing_sha256": self.preprocessing_sha256,
            },
        }

    @classmethod
    def load(cls, cache_dir: Path | None = None, model: str = "bioclip") -> "Screener":
        # Heavy libraries are deliberately outside deterministic Temporal workflow imports.
        import open_clip
        import torch
        from huggingface_hub import snapshot_download

        torch.set_num_threads(4)
        entry = MODELS[model]
        path = Path(
            snapshot_download(
                entry["repo"],
                revision=entry["revision"],
                allow_patterns=["open_clip_config.json", entry["weights"]],
            )
        )
        encoder, _, transform = open_clip.create_model_and_transforms(f"local-dir:{path}")
        weights = file_sha256(path / entry["weights"])
        tokenizer = open_clip.get_tokenizer(entry["tokenizer"])
        preprocessing = {**library_versions(), **open_clip.get_model_preprocess_cfg(encoder)}
        return cls(
            cast(Encoder, encoder),
            transform,
            tokenizer,
            weights,
            cache_dir,
            preprocessing=preprocessing,
            model_key=model,
        )

    def encode_text(self, prompts: list[str]) -> Any:
        with self.torch.inference_mode():
            return self.model.encode_text(self.tokenizer(prompts), normalize=True)

    def cache_path(self, image_bytes: bytes, boxes: list) -> Path | None:
        if self.cache_dir is None:
            return None
        parts = [
            hashlib.sha256(image_bytes).hexdigest(),
            self.metadata["model"],
            self.metadata["revision"],  # the pinned config, not just weights, shapes the encoder
            self.weights_sha256,
            self.preprocessing_sha256,
            json.dumps([list(box) for box in boxes]),
            str(WINDOW_REVISION),
        ]
        return self.cache_dir / f"{hashlib.sha256('|'.join(parts).encode()).hexdigest()}.npy"

    def window_features(self, image: Image.Image, boxes: list, cache: Path | None) -> tuple:
        """Normalised window embeddings, reused from disk when the exact inputs match."""
        if cache is not None and cache.exists():
            try:
                cached = np.load(cache, allow_pickle=False)
                valid = (
                    cached.shape == (len(boxes), self.text.shape[1])
                    and np.issubdtype(cached.dtype, np.floating)
                    and bool(np.isfinite(cached).all())
                )
                if valid:
                    return self.torch.from_numpy(cached), "hit"
            except (OSError, ValueError, EOFError):
                pass  # Corrupt or partial entries are recomputed, never trusted.
        chunks = []
        with self.torch.inference_mode():
            for start in range(0, len(boxes), ENCODE_BATCH):
                views = [square_view(image, box) for box in boxes[start : start + ENCODE_BATCH]]
                batch = self.torch.stack([self.transform(view) for view in views])
                chunks.append(self.model.encode_image(batch, normalize=True))
        features = self.torch.cat(chunks)
        if cache is None:
            return features, "off"
        cache.parent.mkdir(parents=True, exist_ok=True)
        temporary = cache.with_suffix(".tmp.npy")
        np.save(temporary, features.cpu().numpy())
        temporary.replace(cache)
        return features, "miss"

    def screen(self, path: Path, subject: str | None = None) -> dict[str, Any]:
        torch = self.torch
        labels = list(SPECIES) + COMPARISONS
        text = self.text
        if subject:
            labels.append(subject)
            text = torch.cat([text, self.encode_text([prompt(subject)])])
        image_bytes = path.read_bytes()
        with Image.open(io.BytesIO(image_bytes)) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
        boxes = region_boxes(*image.size)
        features, cache_state = self.window_features(
            image, boxes, self.cache_path(image_bytes, boxes)
        )
        with torch.inference_mode():
            scores = (features.to(text.dtype) @ text.T).cpu().numpy()
        # The whole frame always counts; featureless tiles keep their scores but cannot win.
        eligible = [
            index == 0 or not featureless(image.crop(box)) for index, box in enumerate(boxes)
        ]
        result = summarize_scores(scores, boxes, labels, len(SPECIES), eligible)
        result["featureless_windows"] = [index for index, ok in enumerate(eligible) if not ok]
        result["coverage_complete"] = covers_every_pixel(*image.size)
        result["subject_prompt"] = prompt(subject) if subject else None
        result["embedding_cache"] = cache_state
        result["window_similarities"] = scores.tolist()
        result["width"], result["height"] = image.size
        return result
