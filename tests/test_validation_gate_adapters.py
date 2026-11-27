"""Headline gates respect dataset splits and keep the old pooled rows."""

from pathlib import Path

import numpy as np
from PIL import Image

from weedz.contract import Annotation
from weedz.validation import cwfid, imageweeds, inat2021, phenobench, plantclef2024
from weedz.validation.inat2021_data import Item
from weedz.validation.inat2021_models import Prediction
from weedz.validation.metrics import development_floor
from weedz.validation.plantclef2024_data import Photo
from weedz.validation.registry import RunContext
from weedz.validation.splits import split_of

GORSE = "Ulex europaeus"
HEADLINES = ("plantclef_top1_recall", "pilot_cue_recall", "local_cue_recall")


def assert_gates(result, names, development="development", held_out="held-out"):
    rates = {(row.name, row.stratum): row for row in result.metrics}
    assert {row.stratum for row in result.metrics if row.target is not None} == {held_out}
    for name in names:
        dev, held = rates[name, development], rates[name, held_out]
        assert held.target == development_floor(dev.successes, dev.total, held.total, True)
        assert result.configuration[f"gate_development_{name}"] == f"{dev.successes}/{dev.total}"


def test_inat_headlines_use_source_split_only(tmp_path, monkeypatch):
    monkeypatch.setattr(inat2021, "runtime", lambda device: {})
    items = [Item(str(i), "unused", GORSE, "Ulex", "Fabaceae", split_of(str(i))) for i in range(20)]
    result = inat2021.run_check(
        inat2021.SPECIES_ID,
        RunContext(tmp_path, tmp_path),
        items,
        lambda selected: [Prediction((GORSE,), (), GORSE, GORSE) for _ in selected],
    )
    assert_gates(result, HEADLINES)
    assert (
        next(m for m in result.metrics if m.name == "pilot_cue_recall" and m.stratum == "all").total
        == 20
    )


def test_plantclef_gates_ignore_hash_split_and_use_publisher_val_test(tmp_path, monkeypatch):
    monkeypatch.setattr(plantclef2024, "evidence_identity", lambda device: "fixture")
    photos = [
        Photo(
            Item(str(i), "unused", GORSE, "Ulex", "Fabaceae", "development"),
            "val" if i < 10 else "test",
            "bark",
            "unused",
            "cc-by",
            "Author",
            str(i),
        )
        for i in range(20)
    ]
    result = plantclef2024.run_check(
        plantclef2024.SPECIES_ID,
        RunContext(tmp_path, tmp_path),
        photos,
        lambda items: [Prediction((GORSE,), (), GORSE, GORSE) for _ in items],
    )
    assert_gates(result, HEADLINES, "val", "test")


def test_imageweeds_region_and_species_gate_positive_only_halves(tmp_path, monkeypatch):
    note = Annotation(
        id="a",
        supervision="box",
        taxon="Bassia scoparia",
        label="present",
        box=(0, 0, 2, 2),
        origin="source",
    )
    items = [
        imageweeds.Item(str(i), Path("unused"), "sha", str(i), "maize", (note,)) for i in range(20)
    ]
    proposals = {item.source_id: [{"box": [0, 0, 2, 2]}] for item in items}
    monkeypatch.setattr(imageweeds, "load_items", lambda context: (items, {}, 0))
    monkeypatch.setattr(imageweeds, "_proposals", lambda *args: (proposals, {}))
    monkeypatch.setattr(imageweeds, "model_inputs", lambda *args, **kwargs: {})
    monkeypatch.setattr(imageweeds, "release_cuda", lambda: None)
    monkeypatch.setattr(
        imageweeds,
        "species_predictor",
        lambda *args: (
            lambda item: imageweeds.SpeciesEvidence(
                regions=proposals[item.source_id], tight=[[]], masked=[[]]
            )
        ),
    )
    context = RunContext(tmp_path, tmp_path)
    assert_gates(imageweeds.run_regions(context), ("box_recall",))
    assert_gates(
        imageweeds.run_species(context), ("conditional_top1", "image_species_max_score_at5")
    )


def test_phenobench_splits_photos_not_instances(tmp_path, monkeypatch):
    image, semantic, instance = [
        tmp_path / f"{name}.png" for name in ("image", "semantic", "instance")
    ]
    Image.new("RGB", (2, 2)).save(image)
    Image.fromarray(np.array([[1, 0], [2, 0]], dtype=np.uint16)).save(semantic)
    Image.fromarray(np.array([[1, 0], [1, 0]], dtype=np.uint16)).save(instance)
    items = [(str(i), image, semantic, instance) for i in range(20)]
    monkeypatch.setattr(phenobench, "load_items", lambda context: (items, {}))
    monkeypatch.setattr(phenobench, "model_inputs", lambda root: {})
    monkeypatch.setattr(phenobench, "release_cuda", lambda: None)
    result = phenobench.run(RunContext(tmp_path, tmp_path), lambda _: [])
    assert_gates(result, ("instance_recall", "foreground_half_covered"))
    assert (
        next(m for m in result.metrics if m.name == "instance_recall" and m.stratum == "all").total
        == 40
    )


def test_cwfid_train_ids_exclude_overlap():
    assert cwfid.development_ids({"train": [1, 2, 28], "test": [28, 60]}) == ["001", "002"]


def test_cwfid_no_assessed_train_masks_leaves_gate_unset(tmp_path, monkeypatch):
    image = tmp_path / "image.png"
    label = tmp_path / "label.png"
    empty = tmp_path / "empty.png"
    Image.new("RGB", (2, 2)).save(image)
    Image.new("RGB", (2, 2), (0, 255, 0)).save(label)
    Image.new("RGB", (2, 2)).save(empty)
    monkeypatch.setattr(
        cwfid,
        "load_items",
        lambda context, development=False: ([("001", image, empty if development else label)], {}),
    )
    monkeypatch.setattr(cwfid, "model_inputs", lambda root: {})
    monkeypatch.setattr(cwfid, "release_cuda", lambda: None)
    result = cwfid.run(RunContext(tmp_path, tmp_path), lambda _: [])
    assert all(row.target is None for row in result.metrics)
    assert result.configuration["gate_development_foreground_90pct_covered"] == "0/0"
    assert any("no assessed development" in limit for limit in result.limits)


def test_openimages_replays_both_halves_but_gates_only_held_out(tmp_path, monkeypatch):
    from weedz.validation import openimages as adapter
    from weedz.validation.openimages_data import Item, LabelBox

    box = LabelBox((0, 0, 1, 1), False)
    items = [Item(str(i), True, "large", (box,)) for i in range(20)]
    monkeypatch.setattr(adapter, "_metadata", lambda context: ({}, items, {}))
    monkeypatch.setattr(adapter, "_checkpoints", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        adapter, "_images", lambda members, cache: {i.id: Path("unused") for i in members}
    )
    monkeypatch.setattr(adapter, "_cohort_digest", lambda images: "fixture")
    monkeypatch.setattr(
        adapter,
        "_sam_all",
        lambda members, *args: {i.id: adapter.SamPrediction(1, [box.box]) for i in members},
    )
    result = adapter.run_boxes(RunContext(tmp_path, tmp_path, "cuda:0"))
    assert_gates(result, ("sam3_box_recall",), "development", "all")
    assert next(m for m in result.metrics if m.stratum == "all").total == sum(
        split_of(i.id) == "held-out" for i in items
    )


def test_cocostuff_preserves_held_out_sample_and_adds_development(tmp_path, monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace

    from weedz.validation import cocostuff as adapter
    from weedz.validation.metrics import rate

    items = [SimpleNamespace(source_id=str(i), split=split_of(str(i))) for i in range(20)]
    monkeypatch.setattr(
        adapter,
        "dataset",
        lambda *args, **kwargs: nullcontext(SimpleNamespace(items=items, inputs={})),
    )
    monkeypatch.setattr(adapter, "sam_predictor", lambda context: None)
    monkeypatch.setattr(adapter, "release_cuda", lambda: None)
    monkeypatch.setattr(adapter, "model_inputs", lambda *args, **kwargs: {})
    monkeypatch.setattr(
        adapter,
        "_score_images",
        lambda data, members, predict: [
            rate(name, len(members), len(members))
            for name in ("half_covered_images", "component_iou_recall")
        ],
    )
    result = adapter.run_proposals(RunContext(tmp_path, tmp_path, "cuda:0", limit=10))
    assert_gates(result, ("half_covered_images", "component_iou_recall"), "development", "all")
    assert next(m for m in result.metrics if m.stratum == "all").total == min(
        10, sum(i.split == "held-out" for i in items)
    )


def test_roadside_publisher_val_defines_gate_and_all_test_positives_are_held_out(tmp_path):
    from weedz.validation import roadside, roadside_data, roadside_models

    items = [
        roadside_data.Item("v", "val/broom/v", "val", ("Cytisus scoparius",), "development", False),
        roadside_data.Item("t", "test/broom/t", "test", ("Cytisus scoparius",), "held-out", False),
        roadside_data.Item(
            "t2", "test/broom/t2", "test", ("Cytisus scoparius",), "development", False
        ),
        roadside_data.Item(
            "m", "multilabel/m", "multilabel", ("Cytisus scoparius",), "held-out", False
        ),
    ]
    received = []

    def fake(members):
        received.extend(members)
        return [
            roadside_models.Prediction(methods={"tiles_top5": ("Cytisus scoparius",)})
            for _ in members
        ]

    result = roadside.run_check(roadside.SPECIES, RunContext(tmp_path, tmp_path), items, fake)
    assert_gates(result, ("tiles_top5_recall",))
    rows = {(m.name, m.stratum): m for m in result.metrics}
    assert rows["tiles_top5_recall", "all"].total == 2  # Original cohort retained.
    assert rows["tiles_top5_recall", "held-out"].total == 2  # Publisher test only.
    assert rows["tiles_top5_recall", "development"].total == 1
    assert set(i.source_id for i in received) == {"v", "t", "t2", "m"}
