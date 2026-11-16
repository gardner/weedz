"""Official SAM3 still-image concept proposals; concept scores are not mask IoU."""

import base64
import hashlib
import io
import json
import math
from collections import Counter
from collections.abc import Callable
from contextlib import AbstractContextManager, contextmanager, nullcontext
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from PIL import Image, ImageOps

from weedz.segmentation.artifacts import StageArtifacts
from weedz.segmentation.regions import MAX_SOURCE_BYTES, MAX_SOURCE_PIXELS, Region, region_from_mask

CODE_REVISION = "eef6839bcfc3458dd52ea80535dc6bd62aea86b1"
HF_REVISION = "3c879f39826c281e95690f02c7821c4de09afae7"
CHECKPOINT_SHA256 = "9999e2341ceef5e136daa386eecb55cb414446a00ac2b55eb2dfd2f7c3cf8c9e"
SCORE_KIND = "SAM3 sigmoid concept logit multiplied by sigmoid presence score; uncalibrated"


@dataclass(frozen=True)
class Sam3Config:
    prompts: tuple[str, ...] = ("plant", "flower")
    max_side: int = 1024
    max_regions: int = 128
    max_prompt_bytes: int = 8_000_000
    min_area: int = 4
    concept_threshold: float = 0.5
    context_fraction: float = 0.25

    def __post_init__(self) -> None:
        clean = tuple(prompt.strip() for prompt in self.prompts)
        if not 1 <= len(clean) <= 8 or len(set(clean)) != len(clean):
            raise ValueError("Use one to eight distinct bounded prompts")
        if any(not prompt or len(prompt) > 80 for prompt in clean):
            raise ValueError("Prompts must contain one to eighty characters")
        if not 64 <= self.max_side <= 1024 or not 1 <= self.max_regions <= 256:
            raise ValueError("SAM3 image/proposal cap exceeded")
        if not 1 <= self.max_prompt_bytes <= 8_000_000:
            raise ValueError("Serialized prompt retention budget exceeded")
        if not math.isfinite(self.concept_threshold) or not 0 <= self.concept_threshold <= 1:
            raise ValueError("Invalid concept threshold")
        if not 0 <= self.context_fraction <= 1 or self.min_area < 1:
            raise ValueError("Invalid crop context/area policy")
        object.__setattr__(self, "prompts", clean)


def _array(value: Any) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach()
        if value.is_floating_point():
            value = value.float()
        value = value.cpu().numpy()
    return np.asarray(value)


def _validated_output(
    image: Image.Image, raw: dict, config: Sam3Config
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if image.mode != "RGB" or not 0 < image.width * image.height <= MAX_SOURCE_PIXELS:
        raise ValueError("Invalid upright RGB source geometry")
    masks, scores, boxes = (_array(raw[key]) for key in ("masks", "scores", "boxes"))
    if masks.ndim == 4 and masks.shape[1] == 1:
        masks = masks[:, 0]
    if masks.ndim != 3 or masks.dtype != bool or len(masks) > 1000:
        raise ValueError("Invalid SAM3 masks")
    if min(masks.shape[1:]) < 1 or max(masks.shape[1:]) > config.max_side:
        raise ValueError("SAM3 mask geometry exceeds profile")
    height, width = masks.shape[1:]
    if abs(height * image.width - width * image.height) > max(image.size):
        raise ValueError("SAM3 masks differ from source aspect ratio")
    if scores.shape != (len(masks),) or boxes.shape != (len(masks), 4):
        raise ValueError("SAM3 output counts differ")
    if (
        not np.isfinite(scores).all()
        or not np.isfinite(boxes).all()
        or ((scores < 0) | (scores > 1)).any()
    ):
        raise ValueError("Nonfinite or invalid SAM3 model scores")
    return masks, scores, boxes


def _region_bytes(record: dict) -> int:
    return len(json.dumps(record, allow_nan=False).encode()) + 2


def concept_regions(image: Image.Image, prompt: str, raw: dict, config: Sam3Config) -> dict:
    masks, scores, boxes = _validated_output(image, raw, config)
    height, width = masks.shape[1:]
    regions, seen, capped, byte_capped, retained_bytes = [], set(), 0, 0, 0
    for index in np.argsort(-scores, kind="stable"):
        mask = masks[index]
        if scores[index] <= config.concept_threshold or int(mask.sum()) < config.min_area:
            continue
        signature = hashlib.sha256(prompt.encode() + b"\0" + mask.tobytes()).hexdigest()
        if signature in seen:
            continue
        seen.add(signature)
        if len(regions) == config.max_regions:
            capped += 1
            continue
        region = region_from_mask(
            image, mask, {}, max_side=config.max_side, context_fraction=config.context_fraction
        ).record()
        region.pop("mask_quality")
        region.update(
            id=signature,
            prompt=prompt,
            concept_score=float(scores[index]),
            concept_score_kind=SCORE_KIND,
            model_box=(
                boxes[index] * np.array([image.width / width, image.height / height] * 2)
            ).tolist(),
            views={},
        )
        size = _region_bytes(region)
        if retained_bytes + size > config.max_prompt_bytes:
            capped += 1
            byte_capped += 1
            continue
        retained_bytes += size
        regions.append(region)
    exhausted = bool(byte_capped and not regions)
    return {
        "prompt": prompt,
        "status": "failed" if exhausted else "ok" if regions else "empty",
        "regions": regions,
        "raw_count": len(masks),
        "truncated": capped > 0,
        "capped_count": capped,
        "byte_capped_count": byte_capped,
        "retained_region_bytes": retained_bytes,
        **({"failure_type": "OutputBudgetExceeded"} if exhausted else {}),
    }


class Processor(Protocol):
    def set_image(self, image: Image.Image) -> dict: ...
    def reset_all_prompts(self, state: dict) -> None: ...
    def set_text_prompt(self, *, state: dict, prompt: str) -> dict: ...


def _restore_geometry(image: Image.Image, record: dict, config: Sam3Config) -> Region:
    """Recreate checked crop pixels without inventing SAM2 IoU or classifier labels."""
    encoded = record["mask_png"]
    if len(encoded) > 4_000_000:
        raise ValueError("SAM3 mask exceeds resource cap")
    with Image.open(io.BytesIO(base64.b64decode(encoded, validate=True))) as original:
        if original.mode != "RGBA" or max(original.size) > config.max_side:
            raise ValueError("Invalid SAM3 mask geometry")
        mask = np.asarray(original.getchannel("A")) > 0
    raw = {
        "masks": mask[None],
        "scores": np.array([record["concept_score"]]),
        "boxes": np.zeros((1, 4)),
    }
    expected = concept_regions(image, record["prompt"], raw, config)["regions"]
    if not expected:
        raise ValueError("Stored region does not meet its declared concept profile")
    for key in ("id", "box", "context_box", "mask_size", "mask_png", "view_transforms"):
        if expected[0][key] != record[key]:
            raise ValueError("SAM3 region geometry or provenance changed")
    return region_from_mask(
        image, mask, {}, max_side=config.max_side, context_fraction=config.context_fraction
    )


def _decoded_image(encoded: bytes, maximum: int = MAX_SOURCE_BYTES) -> Image.Image:
    if len(encoded) > maximum:
        raise ValueError("Source exceeds the configured SAM3 byte cap")
    try:
        with Image.open(io.BytesIO(encoded)) as original:
            if original.width * original.height > MAX_SOURCE_PIXELS:
                raise ValueError("Source exceeds the 40 megapixel SAM3 profile cap")
            return ImageOps.exif_transpose(original).convert("RGB")
    except Image.DecompressionBombError as error:
        raise ValueError("Source exceeds the SAM3 pixel cap") from error


def _validate_records(records: list[dict], config: Sam3Config) -> None:
    if len(records) > config.max_regions * len(config.prompts):
        raise ValueError("SAM3 record count exceeds the declared prompt/profile budget")
    prompts = [record.get("prompt") for record in records]
    if any(prompt not in config.prompts for prompt in prompts):
        raise ValueError("SAM3 record prompt is outside the declared profile")
    if max(Counter(prompts).values(), default=0) > config.max_regions:
        raise ValueError("SAM3 record count exceeds its per-prompt budget")
    sizes = Counter()
    for record in records:
        sizes[record["prompt"]] += _region_bytes(record)
    if any(size > config.max_prompt_bytes for size in sizes.values()):
        raise ValueError("SAM3 records exceed the declared per-prompt byte budget")


def restore_concept_regions(
    encoded: bytes,
    records: list[dict],
    config: Sam3Config,
    *,
    expected_sha256: str,
    max_source_bytes: int | None = None,
) -> list[Region]:
    """Verify the envelope's exact source, decode once, then restore real crop pixels."""
    from weedz.segmentation.ingress import source_budget

    maximum = source_budget(max_source_bytes)
    if len(encoded) > maximum or hashlib.sha256(encoded).hexdigest() != expected_sha256:
        raise ValueError("SAM3 source checksum or byte cap mismatch")
    _validate_records(records, config)
    image = _decoded_image(encoded, maximum)
    return [_restore_geometry(image, record, config) for record in records]


def restore_concept_region(
    encoded: bytes,
    record: dict,
    config: Sam3Config,
    *,
    expected_sha256: str,
    max_source_bytes: int | None = None,
) -> Region:
    """Single-region convenience wrapper; use plural restoration to decode once/photo."""
    return restore_concept_regions(
        encoded,
        [record],
        config,
        expected_sha256=expected_sha256,
        max_source_bytes=max_source_bytes,
    )[0]


class Sam3Image:
    """Prompt-separated actual image inference with immutable per-prompt evidence."""

    def __init__(
        self,
        processor: Processor,
        config: Sam3Config,
        metadata: dict[str, Any],
        cache: Path,
        context_factory: Callable[[], AbstractContextManager] | None = None,
        *,
        max_source_bytes: int | None = None,
    ) -> None:
        from weedz.segmentation.ingress import proposal_metadata, source_budget

        if "source_ingress" in metadata:
            raise ValueError("Declare SAM3 source ingress with max_source_bytes, not raw metadata")
        self._source_byte_limit = source_budget(max_source_bytes)
        self.processor, self.config, self.cache = processor, config, Path(cache)
        self.context_factory = context_factory or nullcontext
        self.metadata = proposal_metadata(
            {**metadata, "profile": "sam3-image-concept-v1", "config": asdict(config)},
            max_source_bytes,
        )
        self.identity = hashlib.sha256(
            json.dumps(self.metadata, sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
        self.model_version = f"sam3-image-concept-v1:{self.identity}"

    @classmethod
    def load(
        cls,
        checkpoint: Path,
        config: Sam3Config,
        cache: Path,
        *,
        max_source_bytes: int | None = None,
    ) -> "Sam3Image":
        import importlib
        import importlib.metadata

        from weedz.segmentation.ingress import source_budget

        source_budget(max_source_bytes)

        path = Path(checkpoint)
        actual = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                actual.update(block)
        if actual.hexdigest() != CHECKPOINT_SHA256:
            raise ValueError("SAM3 checkpoint checksum mismatch")
        installed = json.loads(
            importlib.metadata.distribution("sam3").read_text("direct_url.json") or "{}"
        )
        if installed.get("vcs_info", {}).get("commit_id") != CODE_REVISION:
            raise ValueError("Install the pinned official SAM3 source")
        torch = importlib.import_module("torch")
        builder = importlib.import_module("sam3.model_builder").build_sam3_image_model
        processor_type = importlib.import_module("sam3.model.sam3_image_processor").Sam3Processor
        torch.cuda.set_device(0)
        torch.set_num_threads(4)
        # Official builder only moves the literal device='cuda', not ordinal strings.
        model = (
            builder(
                checkpoint_path=str(path),
                load_from_HF=False,
                device="cpu",
                compile=False,
                enable_inst_interactivity=False,
            )
            .to("cuda:0")
            .float()
        )
        processor = processor_type(
            model, resolution=1008, device="cuda:0", confidence_threshold=0.0
        )
        metadata = {
            "model": "SAM3 still-image concept segmentation",
            "code_revision": CODE_REVISION,
            "checkpoint_revision": HF_REVISION,
            "checkpoint_sha256": actual.hexdigest(),
            "processor_resolution": 1008,
            "processor_output_threshold": 0.0,
            "mask_probability_threshold": 0.5,
            "score_kind": SCORE_KIND,
            "calibrated": False,
            "device": "cuda:0",
            "precision": "FP32 weights; BF16 CUDA autocast",
            "torch": torch.__version__,
            "numpy": np.__version__,
            "pillow": importlib.metadata.version("pillow"),
            "license": "SAM License 2025-11-19",
            "license_url": f"https://github.com/facebookresearch/sam3/blob/{CODE_REVISION}/LICENSE",
        }

        @contextmanager
        def inference():
            with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
                yield

        return cls(processor, config, metadata, cache, inference, max_source_bytes=max_source_bytes)

    @property
    def source_byte_limit(self) -> int:
        return self._source_byte_limit

    def screen(self, path: Path) -> dict:
        with Path(path).open("rb") as stream:
            encoded = stream.read(self.source_byte_limit + 1)
        source_sha = hashlib.sha256(encoded).hexdigest()
        image = _decoded_image(encoded, self.source_byte_limit)
        prepared = image.copy()
        prepared.thumbnail((self.config.max_side, self.config.max_side), Image.Resampling.LANCZOS)
        artifacts = StageArtifacts(self.cache, f"sam3-{self.identity[:20]}")
        results, hits, state, embedding_failure = [], 0, None, None
        with self.context_factory():
            for prompt in self.config.prompts:
                inputs = {
                    "model_version": self.model_version,
                    "source_sha256": source_sha,
                    "prompt": prompt,
                }
                key = f"{source_sha}:{prompt}"
                cached = artifacts.read("proposals", key, inputs)
                if cached and cached["status"] in {"ok", "empty"}:
                    results.append(cached)
                    hits += 1
                    continue
                if state is None and embedding_failure is None:
                    state, embedding_failure = self._embed(prepared)
                result = (
                    self._prompt(image, state, prompt)
                    if state is not None
                    else {"prompt": prompt, **(embedding_failure or {})}
                )
                results.append(artifacts.write("proposals", key, inputs, result))
        failed = sum(result["status"] == "failed" for result in results)
        regions = [region for result in results for region in result["regions"]]
        status = (
            "failed"
            if failed == len(results)
            else "partial"
            if failed
            else "ok"
            if regions
            else "empty"
        )
        return {
            "schema": 1,
            "status": status,
            "source_sha256": source_sha,
            "model_version": self.model_version,
            "provenance": self.metadata,
            "coordinate_frame": "EXIF-upright original; xyxy right/bottom exclusive",
            "prompts": results,
            "regions": regions,
            "cache_hits": hits,
            "failed_prompts": failed,
            "baseline_retained": False,
        }

    def _embed(self, prepared: Image.Image) -> tuple[dict | None, dict | None]:
        try:
            return self.processor.set_image(prepared), None
        except (ValueError, RuntimeError, OSError, MemoryError) as error:
            return None, {
                "status": "failed",
                "regions": [],
                "failure_type": type(error).__name__,
                "failure_phase": "image_embedding",
            }

    def _prompt(self, image: Image.Image, state: dict, prompt: str) -> dict:
        import time

        start = time.monotonic()
        try:
            self.processor.reset_all_prompts(state)
            raw = self.processor.set_text_prompt(state=state, prompt=prompt)
            result = concept_regions(image, prompt, raw, self.config)
            result["raw_top_concept_scores_before_retention"] = np.sort(_array(raw["scores"]))[
                ::-1
            ][:20].tolist()
        except (ValueError, RuntimeError, OSError, MemoryError) as error:
            result = {
                "prompt": prompt,
                "status": "failed",
                "regions": [],
                "failure_type": type(error).__name__,
            }
        result["elapsed_seconds"] = time.monotonic() - start
        return result
