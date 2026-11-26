import json
from pathlib import Path

import pytest

from weedz.validation.inat2021 import (
    FALSE_ALARMS,
    SPECIES_ID,
    run_check,
    score_false_alarms,
    score_species,
)
from weedz.validation.inat2021_data import Item, load_items, subject_stratum
from weedz.validation.inat2021_models import (
    LOCAL_FLOOR,
    LOCAL_MARGIN,
    PILOT_FLOOR,
    ClipEvidence,
    PlantEvidence,
    Prediction,
    decisions,
)
from weedz.validation.registry import RunContext
from weedz.validation.splits import split_of

GORSE = "Ulex europaeus"
BROOM = "Cytisus scoparius"
VITALBA = "Clematis vitalba"
PAMPAS = "Cortaderia selloana"


@pytest.fixture
def labels(tmp_path: Path) -> Path:
    taxa = [
        (GORSE, "Ulex", "Fabaceae", "Plants"),
        (BROOM, "Cytisus", "Fabaceae", "Plants"),
        (VITALBA, "Clematis", "Ranunculaceae", "Plants"),
        (PAMPAS, "Cortaderia", "Poaceae", "Plants"),
        ("Austroderia richardii", "Austroderia", "Poaceae", "Plants"),
        ("Clematis alpina", "Clematis", "Ranunculaceae", "Plants"),
        ("Genista tinctoria", "Genista", "Fabaceae", "Plants"),
        ("Quercus robur", "Quercus", "Fagaceae", "Plants"),
        ("Apis mellifera", "Apis", "Apidae", "Insects"),
    ]
    ids = [i for i in range(100) if split_of(str(i)) == "held-out"][: len(taxa)]
    path = tmp_path / "val.json"
    path.write_text(
        json.dumps(
            {
                "categories": [
                    dict(id=k, name=name, genus=genus, family=family, supercategory=group)
                    for k, (name, genus, family, group) in enumerate(taxa)
                ],
                "images": [{"id": i, "file_name": f"val/cat/{i}.jpg"} for i in [*ids, 100]],
                "annotations": [{"image_id": i, "category_id": k} for k, i in enumerate(ids)],
            }
        )
    )
    return path


def test_labels_and_negative_strata(labels: Path):
    items = load_items(labels)
    assert [item.taxon for item in items] == [
        GORSE,
        BROOM,
        VITALBA,
        PAMPAS,
        "Austroderia richardii",
        "Clematis alpina",
        "Genista tinctoria",
        "Quercus robur",
    ]
    assert [subject_stratum(item) for item in items] == [
        "target",
        "lookalike",
        "target",
        "target",
        "lookalike",
        "same_genus",
        "same_family",
        "other_plants",
    ]
    assert all(item.split == split_of(item.source_id) == "held-out" for item in items)
    assert items[0].file_name == f"val/cat/{items[0].source_id}.jpg"


def test_rejects_ambiguous_label(labels: Path):
    payload = json.loads(labels.read_text())
    annotation = payload["annotations"][0]
    payload["annotations"].append({**annotation, "category_id": 1})
    labels.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="multiple subject labels"):
        load_items(labels)


def test_frozen_rules_use_inclusive_score_and_agreement():
    plant = PlantEvidence(
        top=(VITALBA, GORSE),
        whole_target=VITALBA,
        tile_target=GORSE,
        tile_index=3,
        tile_score=PILOT_FLOOR,
    )
    clip = ClipEvidence(top=(BROOM, GORSE), tile_target=GORSE, tile_margin=LOCAL_MARGIN)
    assert decisions(plant, clip, GORSE) == (None, GORSE)
    plant = plant.model_copy(update={"whole_target": GORSE})
    assert decisions(plant, clip, GORSE) == (GORSE, GORSE)
    assert decisions(plant, clip, VITALBA) == (None, GORSE)
    plant = plant.model_copy(update={"tile_score": LOCAL_FLOOR})
    assert decisions(plant, clip, GORSE) == (None, GORSE)
    assert decisions(plant, clip.model_copy(update={"tile_target": VITALBA}), GORSE) == (None, None)
    assert decisions(
        plant, clip.model_copy(update={"tile_margin": LOCAL_MARGIN - 0.001}), GORSE
    ) == (None, None)


def fake(items: list[Item]) -> list[Prediction]:
    return [Prediction((GORSE, VITALBA), (BROOM, GORSE), None, GORSE) for _ in items]


def test_scores_correct_recall_and_wrong_subject_cues(labels: Path):
    items = load_items(labels)
    pairs = list(zip(items, fake(items), strict=True))
    species = {(m.name, m.stratum): m for m in score_species(pairs)}
    assert species["plantclef_top1_recall", "all"].successes == 1
    assert species["plantclef_top5_recall", "all"].successes == 2
    assert species["local_cue_recall", "all"].total == 3
    assert species["local_cue_recall", PAMPAS].successes == 0
    assert species["local_cue_confusion", BROOM].successes == 1
    assert species["bioclip_top1_confusion", BROOM].successes == 0

    false = {(m.name, m.stratum): m for m in score_false_alarms(pairs)}
    assert false["local_cue_wrong_subject", "all"].total == 5
    assert false["local_cue_wrong_subject", "all"].ceiling == 0.01
    assert false["local_cue_wrong_subject", "all"].passed is False
    assert false["bioclip_top1_wrong_subject", "same_family"].successes == 0
    assert false["plantclef_top1_wrong_subject", "lookalike"].successes == 2
    assert false["local_cue_worst_species", BROOM].successes == 1


@pytest.mark.parametrize("check,count", [(SPECIES_ID, 5), (FALSE_ALARMS, 5)])
def test_runner_selects_held_out_before_predicting(labels: Path, check: str, count: int):
    items = load_items(labels)
    items.append(Item("0-development", "unused.jpg", GORSE, "Ulex", "Fabaceae", "development"))
    received: list[Item] = []

    def predictor(selected: list[Item]) -> list[Prediction]:
        received.extend(selected)
        return fake(selected)

    result = run_check(check, RunContext(labels.parent, labels.parent), items, predictor)
    assert result.split == "held-out"
    assert len(received) == count
    assert all(item.split == "held-out" for item in received)
    assert all(item.taxon not in {GORSE, VITALBA, PAMPAS} for item in received) == (
        check == FALSE_ALARMS
    )
