"""Choose the operating threshold on validation; score the test set once."""

import math
from collections.abc import Sequence
from typing import TypedDict

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


class Confusion(TypedDict):
    tn: int
    fp: int
    fn: int
    tp: int


class Metrics(TypedDict):
    count: int
    threshold: float
    confusion: Confusion
    precision: float
    recall: float
    f1: float
    accuracy: float
    average_precision: float | None
    roc_auc: float | None


def _validate(labels: Sequence[int], scores: Sequence[float]) -> None:
    if len(labels) != len(scores) or not labels:
        raise ValueError("Need equally sized, nonempty labels and scores")
    if not set(labels) <= {0, 1}:
        raise ValueError("Labels must be binary")
    if any(not math.isfinite(score) or not 0 <= score <= 1 for score in scores):
        raise ValueError("Scores must be finite and between zero and one")


def select_threshold(
    labels: Sequence[int], scores: Sequence[float], *, target_recall: float = 0.9
) -> float:
    _validate(labels, scores)
    if not math.isfinite(target_recall) or not 0 < target_recall <= 1:
        raise ValueError("Target recall must be greater than zero and at most one")
    positives = sorted(score for label, score in zip(labels, scores, strict=True) if label == 1)
    if not positives:
        raise ValueError("Validation needs positive observations to select recall")
    required = math.ceil(target_recall * len(positives))
    return positives[-required]


def evaluate(labels: Sequence[int], scores: Sequence[float], *, threshold: float) -> Metrics:
    _validate(labels, scores)
    if not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("Threshold must be between zero and one")
    truth = np.asarray(labels)
    predicted = np.asarray(scores) >= threshold
    tp = int(np.sum(predicted & (truth == 1)))
    fp = int(np.sum(predicted & (truth == 0)))
    fn = int(np.sum(~predicted & (truth == 1)))
    tn = int(np.sum(~predicted & (truth == 0)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    both_classes = len(set(labels)) == 2
    return {
        "count": len(labels),
        "threshold": threshold,
        "confusion": {"tn": tn, "fp": fp, "fn": fn, "tp": tp},
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "accuracy": (tp + tn) / len(labels),
        "average_precision": float(average_precision_score(labels, scores))
        if both_classes
        else None,
        "roc_auc": float(roc_auc_score(labels, scores)) if both_classes else None,
    }
