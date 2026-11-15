import numpy as np
from PIL import Image

from weedz.segmentation.regions import ProposalConfig, proposals, upright


def test_exif_orientation_is_applied_before_proposal_coordinates(tmp_path):
    image = Image.new("RGB", (8, 4))
    exif = image.getexif()
    exif[274] = 6
    path = tmp_path / "rotated.jpg"
    image.save(path, exif=exif)
    assert upright(path).size == (4, 8)


def test_mask_bounds_context_and_three_views_align_to_upright_original():
    image = Image.new("RGB", (20, 10), (255, 0, 0))
    mask = np.zeros((5, 10), dtype=bool)
    mask[1:4, 2:5] = True
    regions = proposals(
        image,
        [{"segmentation": mask, "predicted_iou": 0.9, "stability_score": 0.95}],
        ProposalConfig(min_area=4),
    )
    assert regions[0].box == (4, 2, 10, 8)
    assert regions[0].context_box == (2, 0, 12, 10)
    assert set(regions[0].views) == {"tight", "masked", "context"}
    assert regions[0].views["tight"].size == (6, 6)
    assert regions[0].mask.shape == (5, 10)


def test_empty_tiny_duplicate_and_overlapping_regions_are_bounded():
    mask = np.zeros((8, 8), dtype=bool)
    mask[1:5, 1:5] = True
    overlapping = np.roll(mask, 2, axis=1)
    raw = [
        {"segmentation": m, "predicted_iou": 0.9, "stability_score": 0.95}
        for m in [np.zeros_like(mask), mask, mask, overlapping]
    ]
    regions = proposals(Image.new("RGB", (8, 8)), raw, ProposalConfig(max_proposals=2))
    assert len(regions) == 2
    assert proposals(Image.new("RGB", (8, 8)), [], ProposalConfig()) == []


def test_config_and_checkpoint_change_cache_identity():
    from weedz.segmentation.regions import cache_key

    first = cache_key(b"photo", "checkpoint-a", ProposalConfig())
    assert first != cache_key(b"photo", "checkpoint-b", ProposalConfig())
    assert first != cache_key(b"photo", "checkpoint-a", ProposalConfig(max_proposals=2))


def test_retained_views_are_bounded_and_transform_provenance_is_explicit():
    mask = np.ones((64, 64), dtype=bool)
    region = proposals(
        Image.new("RGB", (2000, 2000)),
        [{"segmentation": mask, "predicted_iou": 0.9, "stability_score": 0.95}],
        ProposalConfig(max_side=64),
    )[0]
    assert all(max(view.size) <= 64 for view in region.views.values())
    assert region.record()["view_transforms"]["masked"]["source_box"] == [0, 0, 2000, 2000]
    assert region.record()["view_transforms"]["masked"]["resized_size"] == [64, 64]


def test_nonfinite_quality_and_zero_sized_masks_are_refused():
    import pytest

    for mask, quality in [(np.ones((8, 8), bool), float("nan")), (np.zeros((0, 8), bool), 0.9)]:
        with pytest.raises(ValueError):
            proposals(
                Image.new("RGB", (8, 8)),
                [{"segmentation": mask, "predicted_iou": quality, "stability_score": 0.95}],
                ProposalConfig(),
            )
