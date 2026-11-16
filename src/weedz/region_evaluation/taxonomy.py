"""Explicit one-to-one taxon mapping into a checksum-verified model vocabulary."""

import json
from dataclasses import dataclass
from pathlib import Path

from weedz.region_evaluation.classifier_inputs import RegionalClassifications
from weedz.region_evaluation.proposal_inputs import _pinned


@dataclass(frozen=True)
class TaxonomyMapping:
    sha256: str
    source: str
    vocabulary_sha256: str
    mapping: dict[str, str]


def load_taxonomy(
    path: Path, sha256: str, vocabulary: Path, classifier: RegionalClassifications
) -> TaxonomyMapping:
    document = json.loads(_pinned(path, sha256, 1024 * 1024))
    expected = classifier.metadata.get("labels_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("Classifier must pin its released vocabulary")
    if document.get("label_kind") != "taxon" or document.get("model_labels_sha256") != expected:
        raise ValueError("Taxon mapping must name the classifier's exact released vocabulary")
    labels = _pinned(vocabulary, expected, 4 * 1024 * 1024).decode("utf-8").splitlines()
    if (
        len(set(labels)) != len(labels)
        or any(not label.strip() for label in labels)
        or type(classifier.metadata.get("class_count")) is not int
        or classifier.metadata.get("class_count") != len(labels)
    ):
        raise ValueError("Model vocabulary count or uniqueness differs")
    source, mapping = document.get("source"), document.get("mapping")
    if (
        not isinstance(source, str)
        or not source.strip()
        or not isinstance(mapping, dict)
        or not mapping
    ):
        raise ValueError("Declare a source namespace and explicit taxon mapping")
    _validate(mapping, set(labels), classifier)
    return TaxonomyMapping(sha256, source, expected, mapping)


def _validate(mapping: dict, labels: set[str], classifier: RegionalClassifications) -> None:
    if any(
        not isinstance(key, str)
        or not key.strip()
        or not isinstance(value, str)
        or value not in labels
        for key, value in mapping.items()
    ):
        raise ValueError("Mapping has an unsupported source/model taxon")
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Many-to-one taxonomy coarsening requires a separate explicit protocol")
    if any(
        prediction["taxon"] not in labels
        for regions in classifier.rows.values()
        for prediction in regions.values()
    ):
        raise ValueError("Classifier returned a taxon outside its declared vocabulary")
