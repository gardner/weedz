"""Separate region evidence alongside unchanged full-frame/tile baseline scores."""

import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Protocol

from PIL import Image

from weedz.discovery.inference import COMPARISONS, LETTERBOX, prompt, summarize_scores
from weedz.discovery.records import SPECIES
from weedz.segmentation.regions import MAX_SOURCE_PIXELS, ProposalConfig, proposals, upright


class Baseline(Protocol):
    metadata: dict[str, Any]

    def screen(self, path: Path, subject: str | None = None) -> dict[str, Any]: ...


class Proposer(Protocol):
    metadata: dict[str, Any]

    def generate(self, image: Image.Image) -> list[dict[str, Any]]: ...


def identify_views(screener: Any, views: dict[str, Image.Image], subject: str | None) -> dict:
    """Same BioCLIP text comparisons, with each view kept separate (never confidence)."""
    torch = screener.torch
    labels = list(SPECIES) + COMPARISONS
    text = screener.text
    if subject:
        labels.append(subject)
        text = torch.cat([text, screener.encode_text([prompt(subject)])])
    result = {}
    for name, image in views.items():
        side = max(image.size)
        padded = Image.new("RGB", (side, side), LETTERBOX)
        padded.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
        with torch.inference_mode():
            batch = torch.stack([screener.transform(padded)])
            features = screener.model.encode_image(batch, normalize=True)
            scores = (features.to(text.dtype) @ text.T).cpu().numpy()
        result[name] = summarize_scores(scores, [(0, 0, *image.size)], labels, len(SPECIES))
        result[name].pop("box")
        for species in result[name]["species"]:
            species.pop("box")
        result[name]["method"] = f"BioCLIP cosine similarity; one letterboxed {name} proposal view"
    return result


class SegmentedScreen:
    def __init__(self, baseline: Baseline, proposer: Proposer, config: ProposalConfig) -> None:
        self.baseline, self.proposer, self.config = baseline, proposer, config
        self.metadata = {
            **baseline.metadata,
            "proposal_experiment": {
                **proposer.metadata,
                "transforms_revision": 1,
                "config": asdict(config),
                "ranking_policy": (
                    "baseline unchanged; proposal views are separate exploratory evidence"
                ),
            },
        }

    def screen(self, path: Path, subject: str | None = None) -> dict[str, Any]:
        return self._screen(path, subject, None)

    def screen_prepared(
        self, path: Path, image: Image.Image, subject: str | None = None
    ) -> dict[str, Any]:
        """Internal prepared path: caller saved these same upright RGB pixels to path.

        The CLI already checked compressed source bytes before saving its metadata-free
        lossless derivative. That derivative can be larger without adding source pixels.
        """
        return self._screen(path, subject, image)

    def _screen(
        self, path: Path, subject: str | None, prepared: Image.Image | None
    ) -> dict[str, Any]:
        start = time.monotonic()
        experiment: dict[str, Any] = {
            "schema": 1,
            "baseline_retained": True,
            "regions": [],
            "provenance": self.metadata["proposal_experiment"],
            "coordinate_frame": "EXIF-upright original; xyxy right/bottom exclusive",
        }
        try:
            image = upright(path) if prepared is None else prepared
            if image.mode != "RGB" or not 0 < image.width * image.height <= MAX_SOURCE_PIXELS:
                raise ValueError("Prepared pixels exceed upright RGB geometry cap")
            regions = proposals(image, self.proposer.generate(image), self.config)
            experiment["status"] = "ok" if regions else "empty"
            for region in regions:
                record = region.record()
                record["views"] = identify_views(self.baseline, region.views, subject)
                experiment["regions"].append(record)
        except (RuntimeError, ValueError, OSError, MemoryError) as error:
            experiment.update(status="failed", failure_type=type(error).__name__, regions=[])
        experiment["elapsed_seconds"] = time.monotonic() - start
        result = self.baseline.screen(path, subject)
        result["segmentation"] = experiment
        return result
