from PIL import Image

from weedz.segmentation.pipeline import SegmentedScreen
from weedz.segmentation.regions import ProposalConfig


class Baseline:
    metadata = {"revision": "fixed", "segmentation": False}

    def screen(self, path, subject=None):
        return {"margin": 0.12, "box": [0, 0, 8, 8], "width": 8, "height": 8}


class Proposer:
    metadata = {"checkpoint": "tiny"}

    def generate(self, image):
        return []


def test_empty_masks_keep_original_baseline_and_mark_no_proposal(tmp_path):
    path = tmp_path / "image.png"
    Image.new("RGB", (8, 8)).save(path)
    result = SegmentedScreen(Baseline(), Proposer(), ProposalConfig()).screen(path)
    assert result["margin"] == 0.12
    assert result["segmentation"]["status"] == "empty"
    assert result["segmentation"]["baseline_retained"] is True


def test_proposal_failure_keeps_baseline_and_is_not_a_confirmed_negative(tmp_path):
    class Broken(Proposer):
        def generate(self, image):
            raise RuntimeError("device failed")

    path = tmp_path / "image.png"
    Image.new("RGB", (8, 8)).save(path)
    result = SegmentedScreen(Baseline(), Broken(), ProposalConfig()).screen(path)
    assert result["margin"] == 0.12
    assert result["segmentation"]["status"] == "failed"
    assert result["segmentation"]["regions"] == []


def test_segmentation_specific_source_cap_does_not_discard_readable_baseline(tmp_path):
    path = tmp_path / "large-valid.png"
    Image.new("RGB", (8, 8)).save(path)
    with path.open("ab") as output:
        output.write(bytes(20_000_001))
    with Image.open(path) as image:
        image.load()  # Valid baseline-readable image despite the proposal input cap.
    result = SegmentedScreen(Baseline(), Proposer(), ProposalConfig()).screen(path)
    assert result["margin"] == 0.12
    assert result["segmentation"]["status"] == "failed"
    assert result["segmentation"]["failure_type"] == "ValueError"


def test_prepared_upright_pixels_do_not_reapply_compressed_source_limit(tmp_path, monkeypatch):
    import numpy as np

    from weedz.segmentation import regions

    original, derived = tmp_path / "original.jpg", tmp_path / "derived.png"
    Image.fromarray(np.random.default_rng(1).integers(0, 256, (32, 32, 3), dtype=np.uint8)).save(
        original, quality=10
    )
    pixels = regions.upright(original)
    pixels.info.clear()
    pixels.save(derived)
    limit = (original.stat().st_size + derived.stat().st_size) // 2
    monkeypatch.setattr(regions, "MAX_SOURCE_BYTES", limit)
    assert original.stat().st_size < limit < derived.stat().st_size
    pixels = regions.upright(original)
    screen = SegmentedScreen(Baseline(), Proposer(), ProposalConfig())
    assert screen.screen(derived)["segmentation"]["status"] == "failed"
    assert screen.screen_prepared(derived, pixels)["segmentation"]["status"] == "empty"


def test_region_method_describes_one_view_without_claiming_overlapping_tiles():
    from test_discovery_inference import fake_screener

    from weedz.segmentation.pipeline import identify_views

    result = identify_views(fake_screener(), {"masked": Image.new("RGB", (8, 8))}, None)
    assert (
        result["masked"]["method"]
        == "BioCLIP cosine similarity; one letterboxed masked proposal view"
    )
