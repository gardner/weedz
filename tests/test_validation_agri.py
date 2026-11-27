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


def test_all_agricultural_checks_registered():
    import weedz.validation.checks  # noqa: F401
    from weedz.validation.registry import REGISTRY

    assert {
        "imageweeds-region-recovery",
        "imageweeds-species",
        "phenobench-instance-recovery",
        "cwfid-mask-coverage",
    } <= REGISTRY.keys()


def test_phenobench_check_with_fake_predictor_needs_no_gpu(tmp_path, monkeypatch):
    from PIL import Image

    from weedz.validation.registry import RunContext

    image, semantic, instance = [
        tmp_path / f"{name}.png" for name in ("image", "semantic", "instance")
    ]
    Image.new("RGB", (2, 2)).save(image)
    Image.fromarray(np.array([[1, 0], [2, 0]], dtype=np.uint16)).save(semantic)
    Image.fromarray(np.array([[1, 0], [1, 0]], dtype=np.uint16)).save(instance)
    monkeypatch.setattr(
        phenobench,
        "load_items",
        lambda context: (
            [("05-15_fixture.png", image, semantic, instance)],
            {"fixture/labels.png": "abc"},
        ),
    )
    monkeypatch.setattr(phenobench, "model_inputs", lambda root: {})
    monkeypatch.setattr(phenobench, "release_cuda", lambda: None)
    result = phenobench.run(RunContext(tmp_path, tmp_path / "cache"), lambda path: [])
    assert result.check == "phenobench-instance-recovery" and result.split == "validation"
    assert metric(result.metrics, "instance_recall").total == 2
    assert metric(result.metrics, "foreground_half_covered").successes == 0
    assert result.configuration["torch_version"]
    assert result.inputs == {"fixture/labels.png": "abc"}


def test_species_five_slot_budget_does_not_filter_to_truth():
    from weedz.contract import Annotation
    from weedz.species_aggregation import RankedTaxon

    truth = Annotation(
        id="1",
        supervision="box",
        taxon="Bassia scoparia",
        label="present",
        box=(0, 0, 2, 2),
        origin="source",
    )
    item = imageweeds.Item("maize/a", Path("a"), "a", "p", "maize", (truth,))
    ranks = [
        [RankedTaxon(taxon=name, score=score, score_kind="closed_set_softmax_uncalibrated")]
        for name, score in [(f"Other plant{i}", 0.9) for i in range(5)] + [("Bassia scoparia", 0.1)]
    ]
    evidence = imageweeds.SpeciesEvidence(
        regions=[{"box": [0, 0, 2, 2]} for _ in ranks],
        tight=[ranks[-1]],
        masked=ranks,
    )
    rows = imageweeds.species_metrics([item], lambda _: evidence)
    assert metric(rows, "image_species_max_score_at5").successes == 0


def test_species_predictor_uses_pipeline_square_masked_crop(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from PIL import Image

    from weedz.contract import Annotation
    from weedz.discovery.inference import file_sha256
    from weedz.validation.registry import RunContext

    image = tmp_path / "image.png"
    Image.new("RGB", (8, 8)).save(image)
    note = Annotation(
        id="1",
        supervision="box",
        taxon="Bassia scoparia",
        label="present",
        box=(0, 0, 2, 4),
        origin="source",
    )
    item = imageweeds.Item("maize/a", image, file_sha256(image), "pixels", "maize", (note,))
    seen = []

    def classify(images):
        seen.extend(view.size for view in images)
        return [[] for _ in images]

    monkeypatch.setattr(imageweeds, "model_inputs", lambda *args, **kwargs: {})
    monkeypatch.setattr(imageweeds, "identity", lambda *args: "fixture")
    monkeypatch.setattr(imageweeds, "plant_predictor", lambda context: classify)
    monkeypatch.setattr(
        imageweeds,
        "restore_concept_regions",
        lambda *args, **kwargs: [
            SimpleNamespace(views={"masked": Image.new("RGB", (2, 4))}),
        ],
    )
    predict = imageweeds.species_predictor(
        RunContext(tmp_path, tmp_path / "cache"), {item.source_id: [{"box": [0, 0, 2, 4]}]}
    )
    predict(item)
    assert seen == [(2, 4), (4, 4)]  # Legacy source control; real masked-view pipeline.


def test_conditional_id_without_matches_is_unmeasured():
    from weedz.contract import Annotation

    truth = Annotation(
        id="1",
        supervision="box",
        taxon="Bassia scoparia",
        label="present",
        box=(0, 0, 2, 2),
        origin="source",
    )
    item = imageweeds.Item("maize/a", Path("a"), "a", "p", "maize", (truth,))
    evidence = imageweeds.SpeciesEvidence(regions=[], tight=[[]], masked=[])
    rows = imageweeds.species_metrics([item], lambda _: evidence)
    row = metric(rows, "conditional_top1")
    assert row.total == 0 and row.value is None


def test_sam_runtime_bridge_keeps_classifier_overlay_out_of_child(tmp_path, monkeypatch):
    import json

    from weedz.validation import agri_models
    from weedz.validation.registry import RunContext

    runtime = tmp_path / "sam-runtime/bin/python"
    monkeypatch.setenv("WEEDZ_SAM3_PYTHON", str(runtime))
    monkeypatch.setenv("PYTHONPATH", "classifier-overlay")
    calls = []

    def run(command, *, input, text, check, env):
        payload = json.loads(input)
        calls.append(payload)
        assert command[0] == str(runtime) and check and text
        assert env["PYTHONPATH"] == str(Path(agri_models.__file__).resolve().parents[2])
        Path(command[-1]).write_text(
            json.dumps(
                {
                    "regions": [[]],
                    "runtime": {"sam3_runtime_numpy_version": "fixture"},
                }
            )
        )

    monkeypatch.setattr(agri_models.subprocess, "run", run)
    result = agri_models.proposal_batch(
        RunContext(tmp_path, tmp_path / "cache", "cuda:0"), "imageweeds", [tmp_path / "image.png"]
    )
    assert result.regions == [[]]
    assert result.runtime == {"sam3_runtime_numpy_version": "fixture"}
    assert calls[0]["adapter"] == "imageweeds"
