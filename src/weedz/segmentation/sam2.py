"""Lazy official SAM 2.1 image automatic-mask adapter; no optional GPU imports at startup."""

import importlib
import importlib.metadata
import json
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from weedz.discovery.inference import file_sha256
from weedz.segmentation.regions import REVISION, ProposalConfig, cache_key, proposals

CODE_REVISION = "2b90b9f5ceec907a1c18123530e92e794ad901a4"
CHECKPOINT_SHA256 = "7402e0d864fa82708a20fbd15bc84245c2f26dff0eb43a4b5b93452deb34be69"
CONFIG = "configs/sam2.1/sam2.1_hiera_t.yaml"


class Sam2Proposer:
    def __init__(
        self,
        checkpoint: Path,
        expected_sha256: str,
        cache: Path,
        config: ProposalConfig,
        device: str = "cuda:0",
    ) -> None:
        digest = file_sha256(checkpoint)
        if digest != expected_sha256:
            raise ValueError("SAM2 checkpoint checksum mismatch")
        installed = json.loads(
            importlib.metadata.distribution("sam-2").read_text("direct_url.json") or "{}"
        )
        if installed.get("vcs_info", {}).get("commit_id") != CODE_REVISION:
            raise ValueError("Install the pinned official SAM2 source revision")
        self.torch = importlib.import_module("torch")
        builder = importlib.import_module("sam2.build_sam").build_sam2
        generator = importlib.import_module(
            "sam2.automatic_mask_generator"
        ).SAM2AutomaticMaskGenerator
        model = builder(CONFIG, str(checkpoint), device=device, apply_postprocessing=False)
        self.generator = generator(
            model,
            points_per_side=config.points_per_side,
            points_per_batch=config.points_per_batch,
            crop_n_layers=0,
            min_mask_region_area=0,
            output_mode="binary_mask",
        )
        self.config, self.cache, self.device = config, cache, device
        self.metadata = {
            "model": "SAM2.1 Hiera tiny",
            "code_revision": CODE_REVISION,
            "checkpoint_sha256": digest,
            "config": CONFIG,
            "device": device,
            "torch": self.torch.__version__,
            "torchvision": importlib.metadata.version("torchvision"),
            "pillow": importlib.metadata.version("pillow"),
            "numpy": np.__version__,
            "mask_filter": {
                "predicted_iou_threshold": 0.8,
                "stability_threshold": 0.95,
                "box_nms_threshold": 0.7,
                "mask_threshold": 0.0,
            },
            "transforms_revision": REVISION,
            "proposal_config": asdict(config),
            "class_agnostic": True,
            "crop_layers": 0,
            "postprocessing": False,
            "licence": "Apache-2.0",
        }
        self.stamp = json.dumps(self.metadata, sort_keys=True)

    def generate(self, image: Image.Image) -> list[dict[str, Any]]:
        thumbnail = image.copy()
        thumbnail.thumbnail((self.config.max_side, self.config.max_side), Image.Resampling.LANCZOS)
        key = cache_key(thumbnail.tobytes(), self.stamp + str(thumbnail.size), self.config)
        path = self.cache / f"{key}.npz"
        if path.exists():
            try:
                return self._cached(path)
            except (ValueError, OSError, KeyError, EOFError, zipfile.BadZipFile):
                pass
        with self.torch.inference_mode():
            raw = self.generator.generate(np.asarray(thumbnail))
        kept = proposals(image, raw, self.config)
        masks = (
            np.stack([region.mask for region in kept])
            if kept
            else np.zeros((0, *thumbnail.size[::-1]), bool)
        )
        quality = np.array(
            [[r.quality["predicted_iou"], r.quality["stability_score"]] for r in kept]
        )
        quality = quality.reshape((-1, 2))
        self.cache.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp.npz")
        np.savez_compressed(temporary, masks=masks, quality=quality)
        temporary.replace(path)
        return self._cached(path)

    def _cached(self, path: Path) -> list[dict[str, Any]]:
        with np.load(path, allow_pickle=False) as archive:
            masks, quality = archive["masks"], archive["quality"]
        if (
            masks.ndim != 3
            or masks.shape[0] > self.config.max_proposals
            or min(masks.shape[1:]) < 1
            or max(masks.shape[1:]) > self.config.max_side
            or masks.dtype != bool
            or quality.shape != (len(masks), 2)
            or not np.isfinite(quality).all()
        ):
            raise ValueError("Invalid mask cache")
        return [
            {"segmentation": m, "predicted_iou": float(q[0]), "stability_score": float(q[1])}
            for m, q in zip(masks, quality, strict=True)
        ]
