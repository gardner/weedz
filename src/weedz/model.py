"""A CPU logistic baseline persisted as plain JSON instead of Python pickle."""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from weedz.dataset import Observation
from weedz.features import FEATURE_COUNT, FEATURE_VERSION, FloatArray, feature_matrix


@dataclass(frozen=True)
class LinearModel:
    mean: FloatArray
    scale: FloatArray
    coefficients: FloatArray
    intercept: float

    def predict(self, images: list[Path]) -> list[float]:
        matrix = feature_matrix(images)
        logits = (matrix - self.mean) / self.scale @ self.coefficients + self.intercept
        # Clipping protects exp without changing any meaningful decision score.
        return (1 / (1 + np.exp(-np.clip(logits, -700, 700)))).tolist()


def fit_model(observations: list[Observation]) -> LinearModel:
    labels = [row.label for row in observations]
    if set(labels) != {0, 1}:
        raise ValueError("Training needs both present and absent observations")
    matrix = feature_matrix([row.image_path for row in observations])
    scaler = StandardScaler().fit(matrix)
    classifier = LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, random_state=0)
    classifier.fit(scaler.transform(matrix), labels)
    return LinearModel(
        np.asarray(scaler.mean_),
        np.asarray(scaler.scale_),
        np.asarray(classifier.coef_[0]),
        float(np.asarray(classifier.intercept_).reshape(-1)[0]),
    )


def save_model(model: LinearModel, path: Path) -> None:
    payload = {
        "format_version": 1,
        "features": FEATURE_VERSION,
        "mean": model.mean.tolist(),
        "scale": model.scale.tolist(),
        "coefficients": model.coefficients.tolist(),
        "intercept": model.intercept,
    }
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def load_model(path: Path) -> LinearModel:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload["format_version"] != 1 or payload["features"] != FEATURE_VERSION:
        raise ValueError("Unsupported model or feature version")
    arrays = [
        np.asarray(payload[key], dtype=np.float64) for key in ("mean", "scale", "coefficients")
    ]
    if any(array.ndim != 1 or not np.isfinite(array).all() for array in arrays):
        raise ValueError("Invalid model coefficients")
    if any(array.shape != (FEATURE_COUNT,) for array in arrays) or np.any(arrays[1] <= 0):
        raise ValueError("Invalid model dimensions or scales")
    intercept = float(payload["intercept"])
    if not np.isfinite(intercept):
        raise ValueError("Invalid model intercept")
    return LinearModel(arrays[0], arrays[1], arrays[2], intercept)
