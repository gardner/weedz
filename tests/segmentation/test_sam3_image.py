"""SAM3 concept scores, prompt identity and geometry remain independent evidence."""

import numpy as np
import pytest
from PIL import Image

from weedz.segmentation.sam3_image import Sam3Config, concept_regions


def test_sam3_scores_are_not_renamed_to_mask_iou_or_species_confidence():
    mask = np.zeros((1, 1, 6, 10), bool)
    mask[0, 0, 1:3, 2:5] = True
    result = concept_regions(
        Image.new("RGB", (100, 60)),
        "flower",
        {"masks": mask, "scores": np.array([0.75]), "boxes": np.array([[2, 1, 5, 3]])},
        Sam3Config(prompts=("flower",)),
    )
    region = result["regions"][0]
    assert region["box"] == [20, 10, 50, 30]
    assert region["model_box"] == [20, 10, 50, 30]
    assert region["concept_score"] == 0.75
    assert region["prompt"] == "flower"
    assert "mask_quality" not in region
    assert "confidence" not in region


def test_prompt_identity_is_part_of_region_identity():
    raw = {
        "masks": np.ones((1, 1, 8, 8), bool),
        "scores": np.array([0.8]),
        "boxes": np.array([[0, 0, 8, 8]]),
    }
    image = Image.new("RGB", (8, 8))
    flower = concept_regions(image, "flower", raw, Sam3Config())["regions"][0]
    plant = concept_regions(image, "plant", raw, Sam3Config())["regions"][0]
    assert flower["id"] != plant["id"]


def test_concept_output_is_bounded_and_reports_truncation():
    masks = np.zeros((2, 1, 8, 8), bool)
    masks[0, :, :4] = True
    masks[1, :, 4:] = True
    raw = {
        "masks": masks,
        "scores": np.array([0.6, 0.9]),
        "boxes": np.array([[0, 0, 8, 8], [0, 0, 8, 8]]),
    }
    result = concept_regions(Image.new("RGB", (8, 8)), "plant", raw, Sam3Config(max_regions=1))
    assert result["raw_count"] == 2 and result["truncated"] is True
    assert len(result["regions"]) == 1
    assert result["regions"][0]["concept_score"] == 0.9


@pytest.mark.parametrize(
    "prompts", [(), ("",), ("flower", "flower"), tuple(str(i) for i in range(9))]
)
def test_prompt_budget_is_explicit(prompts):
    with pytest.raises(ValueError):
        Sam3Config(prompts=prompts)


def test_prompt_caches_and_resets_are_independent(tmp_path):
    from weedz.segmentation.sam3_image import Sam3Image

    class Processor:
        calls = []
        images = 0

        def set_image(self, image):
            self.images += 1
            return {"size": image.size}

        def reset_all_prompts(self, state):
            self.calls.append("reset")

        def set_text_prompt(self, *, state, prompt):
            assert self.calls[-1] == "reset"
            self.calls.append(prompt)
            w, h = state["size"]
            return {
                "masks": np.ones((1, 1, h, w), bool),
                "scores": np.array([0.8]),
                "boxes": np.array([[0, 0, w, h]]),
            }

    path = tmp_path / "image.png"
    Image.new("RGB", (8, 8)).save(path)
    processor = Processor()
    runner = Sam3Image(processor, Sam3Config(), {"checkpoint": "fixed"}, tmp_path / "cache")
    first = runner.screen(path)
    second = runner.screen(path)
    assert first["status"] == "ok" and second["cache_hits"] == 2
    assert processor.calls == ["reset", "plant", "reset", "flower"] and processor.images == 1
    changed = Sam3Image(
        processor, Sam3Config(prompts=("gorse",)), {"checkpoint": "fixed"}, tmp_path / "cache"
    )
    assert changed.screen(path)["cache_hits"] == 0
    assert processor.calls[-1] == "gorse"


def test_classagnostic_restore_has_real_pixels_without_synthetic_mask_quality():
    from weedz.segmentation.sam3_image import restore_concept_region

    image = Image.new("RGB", (100, 60), "yellow")
    masks = np.zeros((1, 6, 10), bool)
    masks[0, 1:3, 2:5] = True
    config = Sam3Config(prompts=("flower",))
    record = concept_regions(
        image,
        "flower",
        {"masks": masks, "scores": np.array([0.8]), "boxes": np.array([[2, 1, 5, 3]])},
        config,
    )["regions"][0]
    restored = restore_concept_region(image, record, config)
    assert restored.quality == {} and restored.box == (20, 10, 50, 30)
    assert restored.views["tight"].getpixel((0, 0)) == (255, 255, 0)
    record["box"] = [0, 0, 1, 1]
    with pytest.raises(ValueError, match="provenance"):
        restore_concept_region(image, record, config)


def test_empty_retention_preserves_raw_scores_and_exif_upright_frame(tmp_path):
    from weedz.segmentation.sam3_image import Sam3Image

    class Processor:
        def set_image(self, image):
            assert image.size == (3, 2)
            return {}

        def reset_all_prompts(self, state):
            pass

        def set_text_prompt(self, *, state, prompt):
            return {
                "masks": np.ones((1, 2, 3), bool),
                "scores": np.array([0.2]),
                "boxes": np.array([[0, 0, 3, 2]]),
            }

    path = tmp_path / "oriented.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (2, 3)).save(path, exif=exif)
    runner = Sam3Image(Processor(), Sam3Config(prompts=("flower",)), {}, tmp_path / "cache")
    result = runner.screen(path)
    assert result["status"] == "empty" and result["regions"] == []
    assert result["prompts"][0]["raw_top_concept_scores_before_retention"] == [0.2]
    assert runner.screen(path)["cache_hits"] == 1


def test_failed_prompt_is_explicit_and_retried_without_repeating_success(tmp_path):
    from weedz.segmentation.sam3_image import Sam3Image

    class Processor:
        calls = []
        fail = True

        def set_image(self, image):
            return {}

        def reset_all_prompts(self, state):
            pass

        def set_text_prompt(self, *, state, prompt):
            self.calls.append(prompt)
            if prompt == "flower" and self.fail:
                raise RuntimeError("Interrupted GPU work")
            return {
                "masks": np.ones((1, 8, 8), bool),
                "scores": np.array([0.8]),
                "boxes": np.array([[0, 0, 8, 8]]),
            }

    path = tmp_path / "plant.png"
    Image.new("RGB", (8, 8)).save(path)
    processor = Processor()
    runner = Sam3Image(processor, Sam3Config(), {}, tmp_path / "cache")
    partial = runner.screen(path)
    assert partial["status"] == "partial" and partial["failed_prompts"] == 1
    processor.fail = False
    success = runner.screen(path)
    assert success["status"] == "ok" and success["cache_hits"] == 1
    assert processor.calls == ["plant", "flower", "flower"]
