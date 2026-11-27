"""Small source fixtures exercise label meaning without models or downloads."""

from pathlib import Path

import numpy as np
import pytest

from weedz.validation import cwfid, imageweeds, phenobench
from weedz.validation.agri import Tallies, image_coverage


def metric(rows, name, stratum="all"):
    return next(row for row in rows if (row.name, row.stratum) == (name, stratum))


def test_imageweeds_partial_boxes_and_invalid_geometry():
    native = {
        "categories": [{"id": 0, "name": "weed: bassia scoparia"}],
        "annotations": [{"id": 7, "image_id": 1, "category_id": 0, "bbox": [1, 2, 3, 4]}],
    }
    image = {"id": 1, "width": 10, "height": 10}
    boxes = imageweeds.label_boxes(native, image)
    assert len(boxes) == 1 and boxes[0].taxon == "Bassia scoparia"
    assert boxes[0].box == (1, 2, 4, 6) and boxes[0].label == "present"
    native["annotations"][0]["bbox"] = [9, 2, 3, 4]
    with pytest.raises(ValueError, match="outside"):
        imageweeds.label_boxes(native, image)


def test_imageweeds_quarantines_all_pixel_aliases():
    a = imageweeds.Item("soybean/a", Path("a"), "a", "same", "soybean", ())
    b = imageweeds.Item("maize/b", Path("b"), "b", "same", "maize", ())
    c = imageweeds.Item("maize/c", Path("c"), "c", "unique", "maize", ())
    kept, aliases = imageweeds.primary_items([a, b, c])
    assert kept == [c] and aliases == 2


def test_imageweeds_scoring_is_one_to_one_and_positive_only():
    from weedz.contract import Annotation

    box = Annotation(
        id="1",
        supervision="box",
        taxon="Bassia scoparia",
        label="present",
        box=(0, 0, 2, 2),
        origin="source",
    )
    item = imageweeds.Item("maize/a", Path("a"), "a", "p", "maize", (box, box))
    predictions = [{"box": [0, 0, 2, 2]}, {"box": [5, 5, 6, 6]}]
    rows = imageweeds.region_metrics([item], lambda _: predictions)
    assert metric(rows, "box_recall").successes == 1
    assert metric(rows, "box_recall").total == 2
    assert metric(rows, "box_recall", "crop:maize").total == 2
    assert all("precision" not in row.name and "false" not in row.name for row in rows)


def test_species_conditional_and_image_pair_denominators():
    from weedz.contract import Annotation
    from weedz.species_aggregation import RankedTaxon

    def rank(name):
        return [RankedTaxon(taxon=name, score=0.8, score_kind="closed_set_softmax_uncalibrated")]

    truth = Annotation(
        id="a",
        supervision="box",
        taxon="Bassia scoparia",
        label="present",
        box=(0, 0, 2, 2),
        origin="source",
    )
    item = imageweeds.Item("maize/a", Path("a"), "a", "p", "maize", (truth, truth))
    evidence = imageweeds.SpeciesEvidence(
        regions=[{"box": [0, 0, 2, 2]}],
        tight=[rank("Bassia scoparia"), rank("Other plant")],
        masked=[rank("Bassia scoparia")],
    )
    rows = imageweeds.species_metrics([item], lambda _: evidence)
    assert metric(rows, "conditional_top1").total == 1
    assert metric(rows, "conditional_top1").successes == 1
    assert metric(rows, "localized_and_identified").total == 2
    assert metric(rows, "image_species_max_score_at5").total == 1
    assert metric(rows, "source_box_top1").successes == 1
    # Neither unmatched proposals nor other unlabelled species become negatives.
    assert all("precision" not in row.name and "false" not in row.name for row in rows)


def test_phenobench_ids_scoped_by_category_and_partial_labels():
    semantics = np.array([[1, 3, 2, 4, 0]], dtype=np.uint16)
    ids = np.array([[7, 7, 7, 8, 0]], dtype=np.uint16)
    plants = phenobench.instances(semantics, ids)
    assert [(p.category, p.native_id, int(p.mask.sum())) for p in plants] == [
        ("crop", 7, 2),
        ("weed", 7, 1),
        ("weed", 8, 1),
    ]
    assert plants[0].partial and plants[2].partial
    with pytest.raises(ValueError, match="semantic"):
        phenobench.instances(np.array([[5]]), np.array([[1]]))


def test_phenobench_one_to_one_matching_size_and_semantic_strata():
    semantics = np.array([[1, 1, 2, 4], [0, 0, 0, 0]], dtype=np.uint16)
    ids = np.array([[1, 1, 1, 1], [0, 0, 0, 0]], dtype=np.uint16)
    masks = [semantics > 0]  # IoU=.5 with either plant; only one can match.
    tally = Tallies()
    phenobench.score_image(tally, semantics, ids, masks, "05-15")
    rows = tally.metrics()
    assert metric(rows, "instance_recall").total == 2
    assert metric(rows, "instance_recall").successes == 1
    assert metric(rows, "instance_recall", "size:under512").total == 2
    assert metric(rows, "foreground_half_covered").total == 1
    assert metric(rows, "foreground_half_covered", "weed").successes == 1
    assert metric(rows, "foreground_half_covered", "date:05-15").successes == 1


def test_cwfid_test_excludes_train_overlap():
    split = {"train": [2, 28], "test": [1, 28, 60]}
    assert cwfid.test_ids(split) == ["001", "060"]


def test_cwfid_colours_are_sparse_positive_evidence():
    colours = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 0]]], dtype=np.uint8)
    masks = cwfid.positive_masks(colours)
    assert masks["weed"].tolist() == [[True, False, False]]
    assert masks["crop"].tolist() == [[False, True, False]]
    assert masks["assessed"].tolist() == [[True, True, False]]
    colours[0, 2] = (0, 0, 255)
    with pytest.raises(ValueError, match="colour"):
        cwfid.positive_masks(colours)


def test_coverage_counts_images_and_skips_unassessed():
    tally = Tallies()
    truth = np.array([[True, True, False]])
    image_coverage(tally, truth, np.array([[True, False, True]]), "weed")
    image_coverage(tally, truth, np.zeros_like(truth), "weed")
    image_coverage(tally, np.zeros_like(truth), np.ones_like(truth), "weed")
    row = metric(tally.metrics(), "foreground_half_covered", "weed")
    assert (row.successes, row.total) == (1, 2)
    assert row.low is not None and row.high is not None


def test_materialized_asset_is_verified_and_repaired(tmp_path):
    import hashlib

    from weedz.validation.agri import materialize

    inputs = {}
    path = materialize(tmp_path, Path("dataset/labels.txt"), b"human labels", inputs)
    path.write_bytes(b"corruption")
    materialize(tmp_path, Path("dataset/labels.txt"), b"human labels", inputs)
    assert path.read_bytes() == b"human labels"
    assert inputs == {"dataset/labels.txt": hashlib.sha256(b"human labels").hexdigest()}


def test_sam_predictor_calls_pipeline_and_reuses_cache(tmp_path, monkeypatch):
    from PIL import Image

    from weedz.validation import agri_models
    from weedz.validation.registry import RunContext

    calls = []
    verified = []

    class FakeSam:
        def screen(self, path):
            calls.append(path)
            return {"status": "empty", "regions": []}

    monkeypatch.setattr(agri_models, "identity", lambda *args: "fixture")
    monkeypatch.setattr(agri_models, "model_inputs", lambda root: verified.append(root))
    monkeypatch.setattr(agri_models.Sam3Image, "load", lambda *args, **kwargs: FakeSam())
    image = tmp_path / "photo.jpg"
    Image.new("RGB", (8, 8)).save(image)
    context = RunContext(tmp_path, tmp_path / "cache", "cuda:0")
    assert agri_models.sam_predictor(context, "cwfid")(image) == []
    assert agri_models.sam_predictor(context, "cwfid")(image) == []
    assert calls == [image] and verified == [tmp_path, tmp_path]
    rotated = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (8, 8)).save(rotated, exif=exif)
    with pytest.raises(ValueError, match="orientation"):
        agri_models.sam_predictor(context, "cwfid")(rotated)


def test_sam_model_verified_even_with_prediction_cache(tmp_path, monkeypatch):
    import hashlib

    from weedz.validation import agri_models
    from weedz.validation.registry import RunContext

    checkpoint = tmp_path / agri_models.SAM_PATH
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_bytes(b"verified model")
    monkeypatch.setattr(
        agri_models, "CHECKPOINT_SHA256", hashlib.sha256(b"verified model").hexdigest()
    )
    assert agri_models.model_inputs(tmp_path)[str(agri_models.SAM_PATH)]
    checkpoint.write_bytes(b"changed model")
    with pytest.raises(ValueError, match="checksum"):
        agri_models.sam_predictor(RunContext(tmp_path, tmp_path / "cache", "cuda:0"), "cwfid")
