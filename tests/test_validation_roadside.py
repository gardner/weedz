"""Tiny publisher-shaped fixtures; no downloads, checkpoints or GPU."""

from pathlib import Path

import pytest

from weedz.species_aggregation import RankedTaxon
from weedz.validation import roadside, roadside_data, roadside_models
from weedz.validation.registry import RunContext
from weedz.validation.splits import split_of

GROUPS = roadside_data.GROUPS
BROOM = "Cytisus scoparius"


def filename(number: int, longitude: float = 10.0) -> str:
    return f"GT_2020-08-17T08_46_31.000Z_CT_{number}_{longitude}_56.0.jpg"


def csv_file(tmp_path: Path, rows: list[str]) -> Path:
    path = tmp_path / "multilabel.csv"
    path.write_text("image_name;" + ";".join(GROUPS) + "\n" + "\n".join(rows) + "\n")
    return path


def test_blank_csv_cells_and_no_species_folder_are_not_negatives(tmp_path: Path):
    name = filename(1)
    csv = csv_file(tmp_path, [name + ";1;;1;;;"])
    membership = [
        ("multilabel", "dummy_class", name),
        ("test", "2_cytisus_scoparius", filename(2, 11.0)),
        ("test", "7_no_species", filename(3, 12.0)),
        ("train", "1_solidago", filename(4)),
    ]
    items = roadside_data.load_items(csv, membership)
    by_id = {item.source_id: item for item in items}
    assert by_id[name].positives == ("Solidago", "Rosa rugosa")
    assert by_id[filename(2, 11.0)].positives == (BROOM,)
    assert by_id[filename(3, 12.0)].positives == ()
    assert len(items) == 3
    assert all(item.split == split_of(item.source_id) for item in items)
    assert not by_id[name].distance_filtered
    assert by_id[filename(2, 11.0)].distance_filtered


@pytest.mark.parametrize("cell", ["0", "yes", "-1"])
def test_unknown_annotation_values_are_rejected(tmp_path: Path, cell: str):
    name = filename(1)
    csv = csv_file(tmp_path, [name + f";{cell};;;;;"])
    with pytest.raises(ValueError, match="positive or blank"):
        roadside_data.load_items(csv, [("multilabel", "dummy_class", name)])


def test_duplicate_and_unmatched_multilabel_rows_are_rejected(tmp_path: Path):
    row = filename(1) + ";1;;;;;"
    csv = csv_file(tmp_path, [row, row])
    with pytest.raises(ValueError, match="Duplicate"):
        roadside_data.load_items(csv, [])
    csv = csv_file(tmp_path, [row])
    with pytest.raises(ValueError, match="membership"):
        roadside_data.load_items(csv, [])


def test_indexes_are_parsed_without_quick_split_duplicates():
    name = filename(1)
    html = f'<a href="{name}.pth">tensor</a><a href="../">parent</a>'
    assert roadside_data.index_names(html) == [name]
    with pytest.raises(ValueError, match="Duplicate"):
        roadside_data.index_names(html + html)
    with pytest.raises(ValueError, match="filename"):
        roadside_data.position("broken.jpg")


def test_distance_filter_uses_validation_and_other_publisher_cohort(tmp_path: Path):
    multi = filename(1)
    test = filename(2, 11.0)
    csv = csv_file(tmp_path, [multi + ";1;;;;;"])
    membership = [
        ("multilabel", "dummy_class", multi),
        ("test", "1_solidago", test),
        ("val", "1_solidago", filename(3)),
    ]
    items = roadside_data.load_items(csv, membership)
    assert [item.distance_filtered for item in items] == [False, True]
    membership.append(("val", "2_cytisus_scoparius", filename(4, 11.0001)))
    assert not any(item.distance_filtered for item in roadside_data.load_items(csv, membership))


def ranked(taxon: str, score: float) -> RankedTaxon:
    return RankedTaxon(taxon=taxon, score=score, score_kind="closed_set_softmax_uncalibrated")


def test_real_aggregation_spends_budget_on_broad_alternatives_before_group_matching():
    crops = [[ranked("Quercus robur L.", 0.9), ranked("Cytisus scoparius (L.) Link", 0.5)]]
    assert roadside_models.suggestions(crops, budget=1) == ("Quercus robur L.",)
    assert roadside_data.groups_for(roadside_models.suggestions(crops, budget=1)) == set()
    assert roadside_data.groups_for(roadside_models.suggestions(crops, budget=2)) == {BROOM}
    assert roadside_data.groups_for(("Solidago canadensis L.", "Solidago gigantea Aiton")) == {
        "Solidago"
    }


def item(number: int, positives: tuple[str, ...], source: str = "test", far: bool = True):
    name = filename(number)
    return roadside_data.Item(name, f"{source}/dummy/{name}", source, positives, "held-out", far)


def prediction(names: tuple[str, ...]) -> roadside_models.Prediction:
    return roadside_models.Prediction(methods={"tiles_top5": names})


def test_positive_pair_scoring_strata_and_unmeasured_watchlist():
    pairs = [
        (item(1, (BROOM, "Rosa rugosa")), prediction(("Cytisus scoparius (L.) Link",))),
        (item(2, ("Solidago",), "multilabel", False), prediction(("Quercus robur L.",))),
        (item(3, ()), prediction(("Rosa rugosa Thunb.",))),
    ]
    rates = {(m.name, m.stratum): m for m in roadside.score(pairs)}
    metric = rates["tiles_top5_recall", "all"]
    assert (metric.successes, metric.total) == (1, 3)
    assert metric.low is not None and metric.high is not None
    assert metric.low < 1 / 3 < metric.high
    assert rates["tiles_top5_recall", "test/distance-filtered/all"].total == 2
    assert rates["tiles_top5_recall", "all/lookalikes"].successes == 1
    assert rates["tiles_top5_recall", "all/watchlist"].value is None
    assert rates["tiles_top5_recall", "multilabel/Solidago"].total == 1
    assert not any(
        "precision" in metric.name or "false" in metric.name for metric in rates.values()
    )


def test_publisher_cutoffs_are_strict_and_not_a_fixed_budget():
    scores = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
    cutoffs = (0.5,) * 6
    selected = roadside_models.publisher_suggestions(scores, cutoffs)
    assert "Solidago" not in selected
    assert set(selected) == set(GROUPS[1:])


def test_runner_passes_held_out_only_to_fake_and_records_limit(tmp_path: Path):
    items = [item(1, (BROOM,)), item(2, ("Solidago",))]
    items.append(roadside_data.Item("development", "unused", "test", (BROOM,), "development", True))
    received: list[roadside_data.Item] = []

    def fake(selected: list[roadside_data.Item]) -> list[roadside_models.Prediction]:
        received.extend(selected)
        return [prediction(("Cytisus scoparius (L.) Link",)) for _ in selected]

    result = roadside.run_check(
        roadside.SPECIES, RunContext(tmp_path, tmp_path, limit=1), items, fake
    )
    assert received == items[:1]
    assert result.split == "held-out"
    assert result.configuration["limit"] == 1
    assert result.configuration["suggestion_budget"] == 5
    assert result.configuration["torch_version"]
    assert result.configuration["scipy_version"]
    assert any("exhaust" in limit.lower() for limit in result.limits)


def test_download_verifies_existing_and_new_bytes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "image.jpg"
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        roadside_data.fetch_verified(path, "https://example.invalid/image", "0" * 64)
    assert not list(tmp_path.glob("*.part"))


def test_cache_reuses_by_image_bytes_but_verifies_models_on_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    context = RunContext(tmp_path, tmp_path)
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"pixels")
    sources = [source, source]
    calls: list[str] = []

    def loader(_context: RunContext, _baseline: bool):
        calls.append("load")
        return lambda _path: prediction((BROOM,))

    monkeypatch.setattr(roadside_models, "load_predictor", loader)
    monkeypatch.setattr(roadside_models, "verify_models", lambda *_: calls.append("verify") or {})
    first = roadside_models.predict_paths(context, sources, baseline=False)
    assert first == [prediction((BROOM,)), prediction((BROOM,))]
    assert calls == ["verify", "load"]
    calls.clear()
    assert roadside_models.predict_paths(context, sources, baseline=False) == first
    assert calls == ["verify"]

    def tampered(*_args):
        raise ValueError("checkpoint checksum mismatch")

    monkeypatch.setattr(roadside_models, "verify_models", tampered)
    with pytest.raises(ValueError, match="checkpoint checksum"):
        roadside_models.predict_paths(context, sources, baseline=False)


def test_plant_predictor_calls_real_view_geometry_with_fake_classifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import numpy as np
    from PIL import Image

    from weedz.classification import plantclef
    from weedz.discovery.inference import region_boxes

    labels = tuple(name for group in roadside_data.SPECIES for name in group)
    seen: list[tuple[int, int]] = []

    class FakeModel:
        def __init__(self):
            self.labels = (*labels, "Quercus robur L.")

        def predict_selected(self, images, indices):
            seen.extend(image.size for image in images)
            logits = np.zeros((len(images), len(self.labels)))
            logits[:, -1] = 10
            shares = np.full((len(images), len(indices)), 0.01)
            return logits, shares

    monkeypatch.setattr(plantclef.PlantClassifier, "load", lambda *_: FakeModel())
    path = tmp_path / "source.jpg"
    Image.new("RGB", (40, 30), "green").save(path)
    predictor = roadside_models.load_predictor(RunContext(tmp_path, tmp_path), False)
    result = predictor(path)
    assert seen[0] == (40, 30)  # The frame control keeps production centre-crop semantics.
    assert len(seen) == 1 + len(region_boxes(40, 30)) + 16
    assert all(width == height for width, height in seen[1:])
    assert result.methods["tiles_top5"][0] == "Quercus robur L."
    assert len(result.methods["grid_top5"]) == 5


def test_fingerprint_tracks_transitive_pipeline_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from weedz.validation import fingerprint

    context = RunContext(tmp_path, tmp_path)
    before = roadside_models.evidence_identity(context, False)
    original = fingerprint.PACKAGE_ROOT
    paths = fingerprint.imported_sources(Path("validation/roadside.py"))
    assert Path("classification/plantclef.py") in paths
    assert Path("species_aggregation.py") in paths
    assert Path("discovery/inference.py") in paths
    # Version changes must invalidate the cache even if all checkpoints are unchanged.
    real_version = fingerprint.version
    monkeypatch.setattr(fingerprint, "version", lambda name: real_version(name) + ".changed")
    assert roadside_models.evidence_identity(context, False) != before
    assert original.is_dir()


def test_complete_staging_download_recovers_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import hashlib

    monkeypatch.setattr(roadside_data, "urlopen", lambda *_args, **_kwargs: pytest.fail("network"))
    contents = b"finished download before process crash"
    expected = hashlib.sha256(contents).hexdigest()
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / (expected + ".part")).write_bytes(contents)
    path = tmp_path / "image.jpg"
    roadside_data.fetch_verified(path, "https://example.invalid/never-request", expected, staging)
    assert path.read_bytes() == contents


@pytest.mark.parametrize("valid", [True, False])
def test_resumed_download_verifies_bytes_before_publishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, valid: bool
):
    import hashlib
    import io

    expected = hashlib.sha256(b"abcd").hexdigest()
    staging = tmp_path / "staging"
    staging.mkdir()
    partial = staging / (expected + ".part")
    partial.write_bytes(b"ab")

    class Response(io.BytesIO):
        status = 206
        headers = {"Content-Range": "bytes 2-3/4"}

    def fake(request, **_kwargs):
        assert request.headers["Range"] == "bytes=2-"
        return Response(b"cd" if valid else b"zz")

    monkeypatch.setattr(roadside_data, "urlopen", fake)
    destination = tmp_path / "images/source.jpg"
    if valid:
        roadside_data.fetch_verified(destination, "https://example.invalid", expected, staging)
        assert destination.read_bytes() == b"abcd"
    else:
        with pytest.raises(ValueError, match="checksum"):
            roadside_data.fetch_verified(destination, "https://example.invalid", expected, staging)
        assert not destination.exists()
    assert not partial.exists()


def test_publisher_predictor_replays_the_released_head_with_fixture_weights(tmp_path: Path):
    import json

    import torch

    root = tmp_path / "danish-roadside"
    (root / "models").mkdir(parents=True)
    (root / "metadata").mkdir()
    weights = {
        "linear_classif.weight": torch.zeros(6, 768),
        "linear_classif.bias": torch.arange(6, dtype=torch.float32),
    }
    torch.save(weights, tmp_path / roadside_models.XP4_WEIGHTS)
    (root / "metadata/xp4-thresholds.json").write_text(
        json.dumps({"xp4_val": dict.fromkeys(GROUPS, 0.5)})
    )
    path = tmp_path / "features.pth"
    torch.save(torch.zeros(926, 768), path)
    predictor = roadside_models.load_predictor(RunContext(tmp_path, tmp_path), True)
    result = predictor(path)
    assert result.methods["released_cutoffs"] == GROUPS[1:]
    assert result.methods["six_group_top1"] == ("Reynoutria",)
    assert result.inference_seconds > 0


def test_baseline_configuration_describes_feature_head_and_variable_budget(tmp_path: Path):
    result = roadside.run_check(
        roadside.BASELINE,
        RunContext(tmp_path, tmp_path),
        [item(1, (BROOM,))],
        lambda items: [prediction((BROOM,)) for _ in items],
    )
    assert result.configuration["feature_views"] == 926
    assert result.configuration["class_count"] == 6
    assert "variable" in str(result.configuration["suggestion_budget"])
    assert "tile_fraction" not in result.configuration


def test_suggestion_ties_match_the_production_tile_profile():
    from weedz.classification.batch import _aggregate_views

    crops = [[ranked("Rosa rugosa Thunb.", 0.5)], [ranked("Cytisus scoparius (L.) Link", 0.5)]]
    production = _aggregate_views([{"topk": [row.model_dump() for row in crop]} for crop in crops])
    assert roadside_models.suggestions(crops, budget=1) == (production[0]["taxon"],)
