"""CPU BioCLIP screening of full frames plus overlapping regions, without training.

Scores are text/image cosine similarities. A tile is a search window, never a
segmentation mask or a localized plant boundary. No threshold is calibrated yet.
"""

import hashlib
import io
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
from PIL import Image, ImageOps

from weedz.discovery.records import SPECIES

# Bump when image decoding changes, so cached embeddings are not reused.
# Window geometry needs no bump: the exact boxes are part of the cache key.
WINDOW_REVISION = 1
MODEL = "imageomics/bioclip"
REVISION = "ce901ab3c6a913f9e9ef94ce6d27761069f4f01c"
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


class Encoder(Protocol):
    def eval(self) -> Any: ...
    def encode_image(self, image: Any, *, normalize: bool) -> Any: ...
    def encode_text(self, text: Any, *, normalize: bool) -> Any: ...


def region_boxes(width: int, height: int) -> list[tuple[int, int, int, int]]:
    crop_width, crop_height = max(1, round(width * 0.6)), max(1, round(height * 0.6))
    return list(
        dict.fromkeys(
            [
                (0, 0, width, height),
                *(
                    (x, y, x + crop_width, y + crop_height)
                    for y in [0, height - crop_height]
                    for x in [0, width - crop_width]
                ),
            ]
        )
    )


def summarize_scores(
    scores: np.ndarray, boxes: list[tuple[int, int, int, int]], labels: list[str], target_count: int
) -> dict[str, Any]:
    results = []
    for index, species in enumerate(labels[:target_count]):
        margins = scores[:, index] - np.max(scores[:, target_count:], axis=1)
        row = int(np.argmax(margins))
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
        "method": "BioCLIP cosine similarity; full frame + four overlapping windows",
    }


def subject_label(photo: dict[str, Any]) -> str | None:
    """The photo's original subject, so a window showing it is not read as a weed.

    A watchlist target is never its own comparison: reference photos would score zero.
    That includes references identified below species, such as a gorse subspecies.
    """
    taxon = photo.get("original_taxon", "")
    if photo.get("cohort") == "reference" or any(
        taxon == name or taxon.startswith(f"{name} ") for name in SPECIES
    ):
        return None
    names = [taxon, photo.get("original_common_name", "")]
    return ", ".join(name for name in names if name) or None


def prompt(label: str) -> str:
    return f"a photograph of {label}"


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
        self.labels = [f"{name}, {common}" for name, common in SPECIES.items()] + COMPARISONS
        self.prompts = [prompt(label) for label in self.labels]
        self.text = self.encode_text(self.prompts)
        self.cache_dir = cache_dir
        self.weights_sha256 = weights_sha256
        self.preprocessing_sha256 = hashlib.sha256(
            json.dumps(preprocessing, sort_keys=True).encode()
        ).hexdigest()
        self.metadata = {
            "model": MODEL,
            "revision": REVISION,
            "weights_sha256": weights_sha256,
            "device": "cpu",
            "ranking_revision": 3,
            "prompts": self.prompts,
            "subject_prompt": prompt("<original taxon>, <common name>"),
            "target_count": len(SPECIES),
            "regions": "whole image and four 60% width/height overlapping windows",
            "ranking": (
                "maximum target minus best comparison-label cosine similarity per window; "
                "comparisons include the photo's original subject"
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
    def load(cls, cache_dir: Path | None = None) -> "Screener":
        # Heavy libraries are deliberately outside deterministic Temporal workflow imports.
        import open_clip
        import torch
        from huggingface_hub import snapshot_download

        torch.set_num_threads(4)
        path = Path(
            snapshot_download(
                MODEL,
                revision=REVISION,
                allow_patterns=[
                    "open_clip_config.json",
                    "open_clip_pytorch_model.bin",
                ],
            )
        )
        model, _, transform = open_clip.create_model_and_transforms(f"local-dir:{path}")
        weights = hashlib.sha256((path / "open_clip_pytorch_model.bin").read_bytes()).hexdigest()
        tokenizer = open_clip.get_tokenizer("ViT-B-16")
        preprocessing = {
            "open_clip": open_clip.__version__,
            **open_clip.get_model_preprocess_cfg(model),
        }
        return cls(
            cast(Encoder, model),
            transform,
            tokenizer,
            weights,
            cache_dir,
            preprocessing=preprocessing,
        )

    def encode_text(self, prompts: list[str]) -> Any:
        with self.torch.inference_mode():
            return self.model.encode_text(self.tokenizer(prompts), normalize=True)

    def cache_path(self, image_bytes: bytes, boxes: list) -> Path | None:
        if self.cache_dir is None:
            return None
        parts = [
            hashlib.sha256(image_bytes).hexdigest(),
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
                if cached.ndim == 2 and len(cached) == len(boxes):
                    return self.torch.from_numpy(cached), "hit"
            except (OSError, ValueError):
                pass  # Corrupt or partial entries are recomputed, never trusted.
        batch = self.torch.stack([self.transform(image.crop(box)) for box in boxes])
        with self.torch.inference_mode():
            features = self.model.encode_image(batch, normalize=True)
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
        result = summarize_scores(scores, boxes, labels, len(SPECIES))
        result["subject_prompt"] = prompt(subject) if subject else None
        result["embedding_cache"] = cache_state
        result["window_similarities"] = scores.tolist()
        result["width"], result["height"] = image.size
        return result
