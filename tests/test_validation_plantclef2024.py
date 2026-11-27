"""Publisher labels, frozen cohorts and shared iNat scoring, with no model or network."""

import csv
import hashlib
import json
from pathlib import Path

import pytest

from weedz.validation import plantclef2024
from weedz.validation.inat2021_data import Item, subject_stratum
from weedz.validation.inat2021_models import Prediction
from weedz.validation.plantclef2024_data import (
    IMAGE_BASE,
    OTHER_BUDGET,
    SAMPLE_SALT,
    load_photos,
    select_photos,
)
from weedz.validation.registry import REGISTRY, RunContext
from weedz.validation.splits import split_of

GORSE = "Ulex europaeus"
BROOM = "Cytisus scoparius"


def write_labels(path: Path, rows: list[dict[str, str]]) -> Path:
    fields = [
        "image_name",
        "organ",
        "species_id",
        "obs_id",
        "license",
        "author",
        "species",
        "genus",
        "family",
        "learn_tag",
        "image_backup_url",
    ]
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    return path


def row(name: str, taxon: str = GORSE, tag: str = "val", family: str = "Fabaceae"):
    return {
        "image_name": f"{name}.jpg",
        "organ": "bark",
        "species_id": "123",
        "obs_id": name,
        "license": "cc-by-sa",
        "author": "A photographer",
        "species": f"{taxon} L." if taxon else "",
        "genus": taxon.split()[0] if taxon else "",
        "family": family,
        "learn_tag": tag,
        "image_backup_url": f"{IMAGE_BASE}/{tag}/123/{name}.jpg",
    }


@pytest.fixture
def labels(tmp_path: Path) -> Path:
    return write_labels(
        tmp_path / "labels.csv",
        [
            row("gorse-val"),
            row("gorse-test", tag="test"),
            row("train", tag="train"),
            row("broom", BROOM),
            row("clematis", "Clematis alpina", family="Ranunculaceae"),
            row("clover", "Trifolium repens"),
            row("oak", "Quercus robur", family="Fagaceae"),
            row("unlabelled", "", family=""),
        ],
    )


def test_publisher_split_subject_labels_and_strata(labels: Path):
    photos = load_photos(labels)
    assert [p.item.source_id for p in photos] == [
        "gorse-val.jpg",
        "gorse-test.jpg",
        "broom.jpg",
        "clematis.jpg",
        "clover.jpg",
        "oak.jpg",
    ]
    assert [subject_stratum(p.item) for p in photos] == [
        "target",
        "target",
        "lookalike",
        "same_genus",
        "same_family",
        "other_plants",
    ]
    assert photos[1].publisher_split == "test"
    assert photos[1].item.split == split_of("gorse-test.jpg")
    assert photos[0].organ == "bark" and photos[0].licence == "cc-by-sa"
    assert photos[0].author == "A photographer"
    assert photos[0].item.file_name == "images/val/gorse-val.jpg"


@pytest.mark.parametrize(
    "change",
    [
        {"image_name": "../escape.jpg"},
        {"image_backup_url": "https://other.invalid/a.jpg"},
        {"image_backup_url": f"{IMAGE_BASE}/train/123/a.jpg"},
        {"family": ""},
    ],
)
def test_rejects_unsafe_or_incomplete_labelled_rows(tmp_path: Path, change: dict[str, str]):
    with pytest.raises(ValueError):
        load_photos(write_labels(tmp_path / "labels.csv", [row("a") | change]))


def test_rejects_duplicate_image_labels(tmp_path: Path):
    with pytest.raises(ValueError, match="Duplicate"):
        load_photos(write_labels(tmp_path / "labels.csv", [row("a"), row("a", BROOM)]))


def test_other_sample_is_salted_hash_order_and_retains_every_relative(labels: Path):
    photos = load_photos(labels)
    extras = [row(f"oak-{i}", "Quercus robur", family="Fagaceae") for i in range(30)]
    photos += load_photos(write_labels(labels.parent / "extras.csv", extras))
    selected = select_photos(photos, targets=False, other_budget=5)
    assert len(selected) == 8  # broom, same genus, same family, and five others
    assert not any(subject_stratum(p.item) == "target" for p in selected)
    others = [p for p in photos if subject_stratum(p.item) == "other_plants"]
    expected = sorted(
        others, key=lambda p: hashlib.sha256(f"{SAMPLE_SALT}:{p.item.source_id}".encode()).digest()
    )[:5]
    assert {p.item.source_id for p in selected if subject_stratum(p.item) == "other_plants"} == {
        p.item.source_id for p in expected
    }
    assert select_photos(list(reversed(photos)), targets=False, other_budget=5) == selected
    assert OTHER_BUDGET == 5000
    assert len(select_photos(photos, targets=True)) == 3


def fake(items: list[Item]) -> list[Prediction]:
    return [Prediction((GORSE,), (BROOM, GORSE), None, GORSE) for _ in items]


@pytest.mark.parametrize(
    "check,count",
    [
        (plantclef2024.SPECIES_ID, 3),
        (plantclef2024.FALSE_ALARMS, 4),
    ],
)
def test_shared_scoring_with_publisher_strata(labels: Path, check: str, count: int):
    received: list[Item] = []

    def predictor(items: list[Item]) -> list[Prediction]:
        received.extend(items)
        return fake(items)

    result = plantclef2024.run_check(
        check,
        RunContext(labels.parent, labels.parent),
        load_photos(labels),
        predictor,
    )
    assert result.split == "validation" and len(received) == count
    metrics = {(m.name, m.stratum): m for m in result.metrics}
    if check == plantclef2024.SPECIES_ID:
        assert metrics["plantclef_top1_recall", "all"].total == 2
        assert metrics["plantclef_top1_recall", "val"].successes == 1
        assert metrics["plantclef_top1_recall", "test/Ulex europaeus"].total == 1
        assert metrics["bioclip_top5_recall", "test"].successes == 1
        assert metrics["local_cue_confusion", BROOM].successes == 1
        assert metrics["local_cue_recall", "Clematis vitalba"].value is None
        assert json.loads(str(result.configuration["target_organ_counts"]))[GORSE]["val"] == {
            "bark": 1,
        }
    else:
        assert metrics["local_cue_wrong_subject", "all"].total == 4
        assert metrics["local_cue_wrong_subject", "all"].ceiling == 0.01
        assert metrics["local_cue_wrong_subject", "same_genus"].successes == 1
        assert metrics["local_cue_wrong_subject", "test"].value is None
        assert metrics["local_cue_worst_species", BROOM].successes == 1
    assert result.configuration["numpy_version"]
    assert result.configuration["safetensors_version"]
    assert any("subject" in limit for limit in result.limits)
    assert any("model selection" in limit for limit in result.limits)
    assert REGISTRY[check].stage == result.stage


def test_smoke_limit_and_prediction_cardinality(labels: Path):
    photos = load_photos(labels)
    context = RunContext(labels.parent, labels.parent, limit=1)
    result = plantclef2024.run_check(plantclef2024.SPECIES_ID, context, photos, fake)
    assert result.configuration["scored_subjects"] == 1
    with pytest.raises(ValueError):
        plantclef2024.run_check(plantclef2024.SPECIES_ID, context, photos, lambda _: [])
    with pytest.raises(ValueError, match="positive"):
        plantclef2024.run_check(
            plantclef2024.SPECIES_ID,
            RunContext(labels.parent, labels.parent, limit=0),
            photos,
            fake,
        )


def test_missing_library_is_explicit(monkeypatch: pytest.MonkeyPatch):
    from importlib.metadata import PackageNotFoundError

    def missing(_name: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(plantclef2024, "version", missing)
    assert set(plantclef2024.library_versions().values()) == {"not installed"}
