"""Exact source-to-released-vocabulary mappings, never guessed binomial stripping."""

import hashlib
import json
from pathlib import Path

import pytest

from weedz.region_evaluation.classifier_inputs import RegionalClassifications
from weedz.region_evaluation.taxonomy import load_taxonomy


def inputs(root: Path):
    vocabulary = root / "labels.txt"
    vocabulary.write_text("Species alba L.\nSpecies rubra A.\n")
    vocabulary_sha = hashlib.sha256(vocabulary.read_bytes()).hexdigest()
    document = {
        "label_kind": "taxon",
        "source": "test",
        "model_labels_sha256": vocabulary_sha,
        "mapping": {"Species alba": "Species alba L."},
    }
    path = root / "mapping.json"
    path.write_text(json.dumps(document))
    classifier = RegionalClassifications(
        "a" * 64,
        "b" * 64,
        "model:v1",
        {"labels_sha256": vocabulary_sha, "class_count": 2},
        {},
        1,
        (),
    )
    return path, vocabulary, document, classifier


def test_mapping_preserves_exact_source_and_model_taxa(tmp_path: Path) -> None:
    path, vocabulary, _, classifier = inputs(tmp_path)
    result = load_taxonomy(
        path, hashlib.sha256(path.read_bytes()).hexdigest(), vocabulary, classifier
    )
    assert result.mapping == {"Species alba": "Species alba L."}
    assert result.source == "test"


@pytest.mark.parametrize("damage", ["category", "unknown_taxon", "wrong_vocabulary"])
def test_unsupported_or_functional_mapping_refused(tmp_path: Path, damage: str) -> None:
    path, vocabulary, document, classifier = inputs(tmp_path)
    if damage == "category":
        document["label_kind"] = "category"
    elif damage == "unknown_taxon":
        document["mapping"]["Species alba"] = "Invented species"
    else:
        document["model_labels_sha256"] = "0" * 64
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        load_taxonomy(path, hashlib.sha256(path.read_bytes()).hexdigest(), vocabulary, classifier)
