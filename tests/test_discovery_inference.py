"""Geometry and ranking tests do not download a model or infer ground truth."""

from pathlib import Path

import numpy as np
import torch
from PIL import Image

from weedz.discovery.inference import Screener, region_boxes, subject_label, summarize_scores


def test_regions_include_whole_frame_and_cover_edges() -> None:
    boxes = region_boxes(1000, 600)
    assert boxes[0] == (0, 0, 1000, 600)
    assert (0, 0, 600, 360) in boxes
    assert (400, 240, 1000, 600) in boxes
    assert all(0 <= x1 < x2 <= 1000 and 0 <= y1 < y2 <= 600 for x1, y1, x2, y2 in boxes)


def test_summary_preserves_raw_similarity_and_best_region() -> None:
    boxes = [(0, 0, 100, 100), (0, 0, 60, 60)]
    scores = np.array([[0.2, 0.3, 0.25, 0.4], [0.35, 0.2, 0.1, 0.3]])
    result = summarize_scores(scores, boxes, ["weed A", "weed B", "weed C", "lookalike"], 3)
    assert result["best_species"] == "weed A"
    assert result["similarity"] == 0.35
    assert result["margin"] == 0.05
    assert result["box"] == [0, 0, 60, 60]
    assert "probability" not in result
    assert len(result["species"]) == 3


def test_window_selection_uses_comparison_margin_not_raw_target_similarity() -> None:
    # A more target-like crop can be even more like a native/comparison label.
    scores = np.array([[0.4, 0.2, 0.2, 0.6], [0.35, 0.2, 0.1, 0.3]])
    boxes = [(0, 0, 100, 100), (0, 0, 60, 60)]
    result = summarize_scores(scores, boxes, ["weed A", "weed B", "weed C", "lookalike"], 3)
    assert result["box"] == [0, 0, 60, 60]
    assert result["similarity"] == 0.35


class FakeEncoder:
    """Three axes: target weed, the photo's own subject, everything else."""

    def eval(self) -> "FakeEncoder":
        return self

    def encode_image(self, image: torch.Tensor, *, normalize: bool) -> torch.Tensor:
        return torch.tensor([[0.6, 0.8, 0.0]]).repeat(len(image), 1)

    def encode_text(self, text: list[str], *, normalize: bool) -> torch.Tensor:
        def axis(prompt: str) -> list[float]:
            if "Cortaderia selloana" in prompt:
                return [1.0, 0.0, 0.0]
            if "Morus serrator" in prompt:
                return [0.0, 1.0, 0.0]
            return [0.0, 0.0, 1.0]

        return torch.tensor([axis(prompt) for prompt in text])


def fake_screener() -> Screener:
    return Screener(FakeEncoder(), lambda _image: torch.zeros(3), lambda prompts: prompts, "hash")


def test_original_subject_explains_a_window_before_a_weed_does(tmp_path: Path) -> None:
    path = tmp_path / "gannet.jpg"
    Image.new("RGB", (40, 30), (200, 200, 220)).save(path)
    screener = fake_screener()

    without_subject = screener.screen(path)
    with_subject = screener.screen(path, "Morus serrator, Australasian gannet")

    assert without_subject["margin"] > 0
    assert with_subject["margin"] < 0
    assert with_subject["subject_prompt"] == "a photograph of Morus serrator, Australasian gannet"
    assert len(with_subject["window_similarities"][0]) == len(screener.prompts) + 1


def test_comparisons_include_non_vegetation_scenes() -> None:
    prompts = " ".join(fake_screener().prompts).lower()
    for scene in ["sky", "water", "sand", "rock"]:
        assert scene in prompts
    assert fake_screener().metadata["ranking_revision"] == 3


def test_subject_label_uses_taxon_and_optional_common_name() -> None:
    assert (
        subject_label({"original_taxon": "Morus serrator", "original_common_name": "Gannet"})
        == "Morus serrator, Gannet"
    )
    assert subject_label(
        {"original_taxon": "Australopacifica garveyi", "original_common_name": ""}
    ) == ("Australopacifica garveyi")
    assert subject_label({"original_taxon": "", "original_common_name": ""}) is None
