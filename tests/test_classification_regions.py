import json

import numpy as np
import pytest
from PIL import Image
from test_classification_batch import Classifier, corpus

from weedz.classification.regions import classify_region_batch
from weedz.contract import Sample
from weedz.segmentation.sam3_image import Sam3Config, concept_regions


def inputs(tmp_path, *, empty=False):
    manifest, image = corpus(tmp_path)
    sample = Sample.model_validate_json(manifest.read_text())
    config = Sam3Config(prompts=("plant",))
    mask = np.zeros((1, 32, 32), bool)
    mask[:, 5:11, 7:25] = True
    records = concept_regions(
        Image.open(image),
        "plant",
        {"masks": mask, "scores": np.array([0.8]), "boxes": np.array([[7, 5, 25, 11]])},
        config,
    )["regions"]
    from dataclasses import asdict

    row = {
        "sample_id": sample.id,
        "image_sha256": sample.media.sha256,
        "segmentation": {
            "status": "empty" if empty else "ok",
            "provenance": {"model": "SAM3 test", "config": asdict(config)},
            "regions": [] if empty else records,
        },
    }
    proposal = tmp_path / "proposals.jsonl"
    proposal.write_text(json.dumps(row) + "\n")
    return manifest, proposal, row


def test_species_are_classified_from_real_masked_pixels_and_resume(tmp_path):
    manifest, proposal, row = inputs(tmp_path)

    class Inspect(Classifier):
        def predict(self, images, top_k=5):
            assert images[0].size == (18, 18)
            assert images[0].getpixel((0, 0)) == (124, 116, 104)
            assert images[0].getpixel((0, 9)) == (0, 128, 0)
            assert images[0].getpixel((17, 9)) == (0, 128, 0)
            return super().predict(images, top_k)

    model = Inspect()
    model.metadata = {**model.metadata, "preprocessing": {"input_size": (3, 518, 518)}}
    out = tmp_path / "regions.json"
    result = classify_region_batch(manifest, tmp_path, proposal, out, model, "sam3")
    assert classify_region_batch(manifest, tmp_path, proposal, out, model, "sam3") == result
    classified = result["predictions"][0]["regions"][0]
    assert classified["id"] == row["segmentation"]["regions"][0]["id"]
    assert classified["topk"] == classified["views"]["masked"]
    assert "mask_quality" not in classified and "annotations" not in result
    assert model.calls == 1
    assert result["model"]["crop_geometry_revision"] == 2
    assert result["model"]["masked_view_policy"]["padding"] == "centred square"


def test_empty_segmentation_never_becomes_an_absence_label(tmp_path):
    manifest, proposal, _ = inputs(tmp_path, empty=True)
    model = Classifier()
    result = classify_region_batch(manifest, tmp_path, proposal, tmp_path / "out", model, "sam3")
    assert result["predictions"][0]["regions"] == []
    assert model.calls == 0


def test_mask_or_source_changes_cannot_reuse_completed_scores(tmp_path):
    manifest, proposal, row = inputs(tmp_path)
    out = tmp_path / "out"
    classify_region_batch(manifest, tmp_path, proposal, out, Classifier(), "sam3")
    row["segmentation"]["regions"][0]["box"] = [0, 0, 1, 1]
    proposal.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="provenance"):
        classify_region_batch(manifest, tmp_path, proposal, out, Classifier(), "sam3")
    out.unlink()
    with pytest.raises(ValueError, match="provenance"):
        classify_region_batch(manifest, tmp_path, proposal, out, Classifier(), "sam3")


def test_missing_and_failed_segmentation_rows_are_rejected(tmp_path):
    manifest, proposal, row = inputs(tmp_path)
    proposal.write_text("")
    with pytest.raises(ValueError, match="Incomplete"):
        classify_region_batch(manifest, tmp_path, proposal, tmp_path / "out", Classifier(), "sam3")
    row["segmentation"]["status"] = "failed"
    proposal.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="completed"):
        classify_region_batch(manifest, tmp_path, proposal, tmp_path / "out", Classifier(), "sam3")


@pytest.mark.parametrize("damage", ["wrong_box", "duplicate_id"])
def test_explicit_legacy_cache_adoption_still_validates_source_masks(tmp_path, damage):
    import hashlib

    manifest, proposal, row = inputs(tmp_path)
    out = tmp_path / "out"
    cached = classify_region_batch(manifest, tmp_path, proposal, out, Classifier(), "sam3")
    cached.pop("result_sha256")
    if damage == "wrong_box":
        row["segmentation"]["regions"][0]["box"] = [0, 0, 1, 1]
    else:
        row["segmentation"]["regions"].append(row["segmentation"]["regions"][0])
        cached["predictions"][0]["regions"].append(cached["predictions"][0]["regions"][0])
    proposal.write_text(json.dumps(row) + "\n")
    cached["proposals_sha256"] = hashlib.sha256(proposal.read_bytes()).hexdigest()
    out.write_text(json.dumps(cached))
    with pytest.raises(ValueError, match="provenance|identities"):
        classify_region_batch(
            manifest,
            tmp_path,
            proposal,
            out,
            Classifier(),
            "sam3",
            verified_existing_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
        )


def test_one_prompt_cannot_consume_another_prompts_region_budget(tmp_path):
    from dataclasses import asdict, replace

    manifest, proposal, row = inputs(tmp_path)
    masks = np.zeros((2, 32, 32), bool)
    masks[0, 2:6, 2:6] = True
    masks[1, 10:14, 10:14] = True
    config = Sam3Config(prompts=("plant", "flower"), max_regions=2)
    stage = row["segmentation"]
    stage["regions"] = concept_regions(
        Image.new("RGB", (32, 32), "green"),
        "plant",
        {
            "masks": masks,
            "scores": np.array([0.9, 0.8]),
            "boxes": np.array([[2, 2, 6, 6], [10, 10, 14, 14]]),
        },
        config,
    )["regions"]
    stage["provenance"]["config"] = asdict(replace(config, max_regions=1))
    proposal.write_text(json.dumps(row) + "\n")
    model = Classifier()
    with pytest.raises(ValueError, match="per-prompt"):
        classify_region_batch(manifest, tmp_path, proposal, tmp_path / "out", model, "sam3")
    assert model.calls == 0
