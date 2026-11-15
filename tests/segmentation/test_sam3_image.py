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
    import hashlib
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = buffer.getvalue()
    expected_sha = hashlib.sha256(encoded).hexdigest()
    restored = restore_concept_region(encoded, record, config, expected_sha256=expected_sha)
    assert restored.quality == {} and restored.box == (20, 10, 50, 30)
    assert restored.views["tight"].getpixel((0, 0)) == (255, 255, 0)
    record["box"] = [0, 0, 1, 1]
    with pytest.raises(ValueError, match="provenance"):
        restore_concept_region(encoded, record, config, expected_sha256=expected_sha)


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


def test_restoration_rejects_wrong_same_sized_source_before_crops():
    import hashlib
    import io

    from weedz.segmentation.sam3_image import restore_concept_regions

    original, changed = io.BytesIO(), io.BytesIO()
    Image.new("RGB", (8, 8), "green").save(original, format="PNG")
    Image.new("RGB", (8, 8), "red").save(changed, format="PNG")
    with pytest.raises(ValueError, match="checksum"):
        restore_concept_regions(
            changed.getvalue(),
            [],
            Sam3Config(),
            expected_sha256=hashlib.sha256(original.getvalue()).hexdigest(),
        )


def test_image_embedding_failure_is_explicit_for_every_uncached_prompt(tmp_path):
    from weedz.segmentation.sam3_image import Sam3Image

    class Processor:
        calls = 0

        def set_image(self, image):
            self.calls += 1
            raise RuntimeError("Transient CUDA embedding failure")

        def reset_all_prompts(self, state):
            pytest.fail("No prompt inference without image embeddings")

        def set_text_prompt(self, *, state, prompt):
            pytest.fail("No prompt inference without image embeddings")

    path = tmp_path / "plant.png"
    Image.new("RGB", (8, 8)).save(path)
    processor = Processor()
    runner = Sam3Image(processor, Sam3Config(), {}, tmp_path / "cache")
    result = runner.screen(path)
    assert result["status"] == "failed" and result["failed_prompts"] == 2
    assert processor.calls == 1
    assert {r["failure_phase"] for r in result["prompts"]} == {"image_embedding"}
    assert runner.screen(path)["status"] == "failed"
    assert processor.calls == 2


def test_plural_restoration_hashes_and_decodes_the_source_once(monkeypatch):
    import hashlib
    import io

    from weedz.segmentation.sam3_image import restore_concept_regions

    image = Image.new("RGB", (8, 8), "green")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = buffer.getvalue()
    config = Sam3Config()
    raw = {
        "masks": np.ones((1, 8, 8), bool),
        "scores": np.array([0.8]),
        "boxes": np.array([[0, 0, 8, 8]]),
    }
    records = [concept_regions(image, p, raw, config)["regions"][0] for p in config.prompts]
    original_open = Image.open
    source_decodes = []

    def observed(stream, *args, **kwargs):
        if isinstance(stream, io.BytesIO) and stream.getvalue() == encoded:
            source_decodes.append(True)
        return original_open(stream, *args, **kwargs)

    monkeypatch.setattr(Image, "open", observed)
    regions = restore_concept_regions(
        encoded, records, config, expected_sha256=hashlib.sha256(encoded).hexdigest()
    )
    assert len(regions) == 2 and source_decodes == [True]


def test_checkpoint_startup_failure_does_not_become_a_negative_result(tmp_path):
    from weedz.segmentation.sam3_image import Sam3Image

    checkpoint = tmp_path / "invalid.pt"
    checkpoint.write_bytes(b"not the pinned checkpoint")
    with pytest.raises(ValueError, match="checkpoint checksum"):
        Sam3Image.load(checkpoint, Sam3Config(), tmp_path / "cache")
    assert not (tmp_path / "cache").exists()


@pytest.mark.parametrize("budget,retained,status", [(1000, 1, "ok"), (100, 0, "failed")])
def test_serialized_retention_budget_fits_artifact_and_reports_truncation(
    tmp_path, monkeypatch, budget, retained, status
):
    from weedz.segmentation import artifacts
    from weedz.segmentation.sam3_image import Sam3Image

    monkeypatch.setattr(artifacts, "MAX_ARTIFACT_BYTES", 2100)

    class Processor:
        def set_image(self, image):
            return {}

        def reset_all_prompts(self, state):
            pass

        def set_text_prompt(self, *, state, prompt):
            masks = np.zeros((2, 1, 8, 8), bool)
            masks[0, :, :4] = True
            masks[1, :, 4:] = True
            return {
                "masks": masks,
                "scores": np.array([0.9, 0.8]),
                "boxes": np.array([[0, 0, 8, 8], [0, 0, 8, 8]]),
            }

    path = tmp_path / "plant.png"
    Image.new("RGB", (8, 8)).save(path)
    config = Sam3Config(prompts=("plant",), max_regions=256, max_prompt_bytes=budget)
    runner = Sam3Image(Processor(), config, {}, tmp_path / "cache")
    result = runner.screen(path)
    prompt = result["prompts"][0]
    assert result["status"] == status and len(result["regions"]) == retained
    assert prompt["truncated"] is True and prompt["byte_capped_count"] == 2 - retained


@pytest.mark.parametrize("unknown_prompt", [False, True])
def test_restoration_enforces_prompt_membership_and_each_prompt_cap(unknown_prompt):
    import hashlib
    import io

    from weedz.segmentation.sam3_image import restore_concept_regions

    image = Image.new("RGB", (8, 8))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = buffer.getvalue()
    config = Sam3Config(prompts=("plant", "flower"), max_regions=1)
    prompt = "gorse" if unknown_prompt else "plant"
    raw = {
        "masks": np.ones((1, 8, 8), bool),
        "scores": np.array([0.8]),
        "boxes": np.array([[0, 0, 8, 8]]),
    }
    record = concept_regions(image, prompt, raw, config)["regions"][0]
    records = [record] if unknown_prompt else [record, record]
    with pytest.raises(ValueError, match="prompt"):
        restore_concept_regions(
            encoded, records, config, expected_sha256=hashlib.sha256(encoded).hexdigest()
        )


def test_restoration_enforces_combined_serialized_bytes_for_each_prompt():
    import hashlib
    import io

    from weedz.segmentation.sam3_image import restore_concept_regions

    image = Image.new("RGB", (8, 8))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = buffer.getvalue()
    masks = np.zeros((2, 1, 8, 8), bool)
    masks[0, :, :4] = True
    masks[1, :, 4:] = True
    records = concept_regions(
        image,
        "plant",
        {
            "masks": masks,
            "scores": np.array([0.9, 0.8]),
            "boxes": np.array([[0, 0, 8, 8], [0, 0, 8, 8]]),
        },
        Sam3Config(),
    )["regions"]
    assert len(records) == 2
    with pytest.raises(ValueError, match="byte"):
        restore_concept_regions(
            encoded,
            records,
            Sam3Config(max_regions=2, max_prompt_bytes=1000),
            expected_sha256=hashlib.sha256(encoded).hexdigest(),
        )
