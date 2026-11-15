"""Geometry and ranking tests do not download a model or infer ground truth."""

from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from weedz.discovery.inference import (
    ENCODE_BATCH,
    LETTERBOX,
    MAX_TILES,
    Screener,
    covers_every_pixel,
    featureless,
    region_boxes,
    square_view,
    subject_label,
    summarize_scores,
)


def tiles_cover_every_pixel(width: int, height: int) -> bool:
    seen = np.zeros((height, width), bool)
    for x1, y1, x2, y2 in region_boxes(width, height)[1:]:
        seen[y1:y2, x1:x2] = True
    return bool(seen.all())


@pytest.mark.parametrize("size", [(1024, 768), (768, 1024), (485, 1024), (1024, 576), (633, 616)])
def test_square_tiles_cover_the_whole_photo_with_overlap(size: tuple[int, int]) -> None:
    width, height = size
    boxes = region_boxes(width, height)
    assert boxes[0] == (0, 0, width, height)
    tiles = boxes[1:]
    side = round(min(width, height) * 0.6)
    assert all(x2 - x1 == side and y2 - y1 == side for x1, y1, x2, y2 in tiles)
    assert all(x1 >= 0 and y1 >= 0 and x2 <= width and y2 <= height for x1, y1, x2, y2 in tiles)
    assert tiles_cover_every_pixel(width, height)
    xs = sorted({x1 for x1, _, _, _ in tiles})
    assert all(b - a <= side * 0.75 + 1 for a, b in zip(xs, xs[1:], strict=False))


def test_tile_counts_follow_the_photo_shape() -> None:
    assert len(region_boxes(1024, 768)) == 1 + 6
    assert len(region_boxes(485, 1024)) == 1 + 10


def test_the_whole_frame_reaches_the_model_as_a_letterboxed_square() -> None:
    image = Image.new("RGB", (40, 20), (200, 0, 0))
    view = square_view(image, (0, 0, 40, 20))
    assert view.size == (40, 40)
    assert view.getpixel((20, 10)) == (200, 0, 0)
    assert view.getpixel((20, 1)) == LETTERBOX


def test_panorama_padding_is_bounded_before_crop_or_canvas_allocation(monkeypatch) -> None:
    image = Image.new("RGB", (1, 100_000))

    def unexpected_allocation(*args, **kwargs):
        pytest.fail("Oversized square must be rejected before allocating any view")

    monkeypatch.setattr(Image.Image, "crop", unexpected_allocation)
    monkeypatch.setattr(Image, "new", unexpected_allocation)
    with pytest.raises(ValueError, match="Square view exceeds the pixel cap"):
        square_view(image, (0, 0, 1, 100_000))


@pytest.mark.parametrize("size", [(9000, 1000), (12000, 300)])
def test_published_panorama_geometries_still_reach_the_letterbox(size, monkeypatch) -> None:
    from unittest.mock import Mock

    # Intercept allocations so this compatibility test need not materialize 144M pixels.
    image, crop, canvas = Mock(), Mock(), Mock()
    image.crop.return_value = crop
    crop.size, crop.width, crop.height = size, *size
    allocate = Mock(return_value=canvas)
    monkeypatch.setattr(Image, "new", allocate)
    assert square_view(image, (0, 0, *size)) is canvas
    allocate.assert_called_once_with("RGB", (size[0], size[0]), LETTERBOX)
    canvas.paste.assert_called_once_with(crop, (0, (size[0] - size[1]) // 2))


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
    return Screener(
        FakeEncoder(),
        lambda _image: torch.zeros(3),
        lambda prompts: prompts,
        "hash",
        preprocessing={},
    )


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
    assert fake_screener().metadata["ranking_revision"] == 4


def test_subject_label_uses_taxon_and_optional_common_name() -> None:
    assert (
        subject_label({"original_taxon": "Morus serrator", "original_common_name": "Gannet"})
        == "Morus serrator, Gannet"
    )
    assert subject_label(
        {"original_taxon": "Australopacifica garveyi", "original_common_name": ""}
    ) == ("Australopacifica garveyi")
    assert subject_label({"original_taxon": "", "original_common_name": ""}) is None


def test_a_watchlist_subject_is_not_compared_against_itself() -> None:
    # Reference photos are labelled with the target; comparing it with itself zeroes the margin.
    photo = {"original_taxon": "Ulex europaeus", "original_common_name": "gorse"}
    assert subject_label(photo) is None


def test_a_target_identified_below_species_is_not_compared_against_itself() -> None:
    photo = {"original_taxon": "Ulex europaeus europaeus", "original_common_name": "Common Gorse"}
    assert subject_label(photo) is None


def test_a_reference_photo_never_gets_a_subject_comparison() -> None:
    photo = {"cohort": "reference", "original_taxon": "Ulex", "original_common_name": "gorses"}
    assert subject_label(photo) is None


def test_a_taxon_sharing_a_target_prefix_is_still_compared() -> None:
    photo = {"original_taxon": "Ulex europaeusoides", "original_common_name": ""}
    assert subject_label(photo) == "Ulex europaeusoides"


def test_featureless_tiles_cannot_win_a_weed_ranking() -> None:
    boxes = [(0, 0, 100, 100), (0, 0, 60, 60), (40, 40, 100, 100)]
    scores = np.array([[0.30, 0.2, 0.2, 0.3], [0.50, 0.2, 0.2, 0.3], [0.33, 0.2, 0.2, 0.3]])
    labels = ["weed A", "weed B", "weed C", "comparison"]
    result = summarize_scores(scores, boxes, labels, 3, eligible=[True, False, True])
    assert result["box"] == [40, 40, 100, 100]
    assert result["margin"] == pytest.approx(0.03)


def test_a_uniform_tile_is_featureless_and_a_textured_one_is_not() -> None:
    dark = Image.new("RGB", (50, 50), (3, 3, 3))
    assert featureless(dark)
    textured = Image.effect_noise((50, 50), 40).convert("RGB")
    assert not featureless(textured)


def test_extreme_panoramas_are_capped_and_flagged() -> None:
    boxes = region_boxes(2048, 10)
    assert len(boxes) <= 1 + MAX_TILES
    assert not covers_every_pixel(2048, 10)
    assert covers_every_pixel(1024, 768)


class CountingBatches(FakeEncoder):
    def __init__(self) -> None:
        self.batches: list[int] = []

    def encode_image(self, image: torch.Tensor, *, normalize: bool) -> torch.Tensor:
        self.batches.append(len(image))
        return super().encode_image(image, normalize=normalize)


def test_windows_are_encoded_in_bounded_batches(tmp_path: Path) -> None:
    path = tmp_path / "tall.jpg"
    Image.effect_noise((300, 1600), 40).convert("RGB").save(path)
    encoder = CountingBatches()
    screener = Screener(
        encoder, lambda _image: torch.zeros(3), lambda p: p, "hash", preprocessing={}
    )
    result = screener.screen(path)
    assert len(encoder.batches) > 1 and max(encoder.batches) <= ENCODE_BATCH
    assert sum(encoder.batches) == len(result["window_similarities"])
    assert result["coverage_complete"] is True


def test_metadata_does_not_claim_full_coverage_unconditionally() -> None:
    regions = fake_screener().metadata["regions"]
    assert "coverage_complete" in regions and str(MAX_TILES) in regions
