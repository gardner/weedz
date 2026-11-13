"""A complete reproducible experiment on the pinned Leafy Spurge crops."""

import json
import platform
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from typing import TypedDict

from weedz.dataset import read_observations
from weedz.evaluation import Metrics, evaluate, select_threshold
from weedz.model import fit_model, load_model, save_model
from weedz.partition import partition_observations
from weedz.provenance import checksum, verify_dataset
from weedz.report import prediction, write_map, write_predictions


class RunMetrics(TypedDict):
    validation: Metrics
    test: Metrics
    majority_test_accuracy: float


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run_pipeline(data_dir: Path, output_dir: Path, *, target_recall: float = 0.9) -> RunMetrics:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"Output directory must be empty to preserve experiments: {output_dir}")
    manifest = verify_dataset(data_dir)
    observations = read_observations(data_dir)
    partitions = partition_observations(observations)
    model = fit_model(partitions.fit)
    validation_scores = model.predict([row.image_path for row in partitions.validation])
    threshold = select_threshold(
        [row.label for row in partitions.validation], validation_scores, target_recall=target_recall
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    save_model(model, output_dir / "model.json")
    # Predictions use the saved model, exercising exactly what a later consumer loads.
    model = load_model(output_dir / "model.json")
    scores = model.predict([row.image_path for row in observations])
    score_by_id = {row.sample_id: score for row, score in zip(observations, scores, strict=True)}
    majority = int(sum(row.label for row in partitions.fit) >= len(partitions.fit) / 2)
    metrics: RunMetrics = {
        "validation": evaluate(
            [row.label for row in partitions.validation], validation_scores, threshold=threshold
        ),
        "test": evaluate(
            [row.label for row in partitions.test],
            [score_by_id[row.sample_id] for row in partitions.test],
            threshold=threshold,
        ),
        "majority_test_accuracy": sum(row.label == majority for row in partitions.test)
        / len(partitions.test),
    }
    predictions = [
        prediction(row, partition, score_by_id[row.sample_id], threshold)
        for partition, rows in partitions.items().items()
        for row in rows
    ]
    write_predictions(predictions, output_dir)
    write_map(predictions, observations, output_dir, metrics["test"])
    _write_json(output_dir / "metrics.json", metrics)
    _write_json(
        output_dir / "run.json",
        {
            "created_at": datetime.now(UTC).isoformat(),
            "dataset": manifest,
            "model": "standardized colour/texture features + balanced logistic regression (C=1)",
            "model_sha256": checksum(output_dir / "model.json"),
            "source_files": {
                path.name: checksum(path)
                for path in sorted(Path(__file__).parent.iterdir())
                if path.suffix in {".py", ".html"}
            },
            "threshold": threshold,
            "target_validation_recall": target_recall,
            "spatial_buffer_m": 2.0,
            "partitions": {
                name: [row.sample_id for row in rows] for name, rows in partitions.items().items()
            },
            "environment": {
                "python": platform.python_version(),
                **{
                    package: version(package)
                    for package in ("numpy", "pillow", "scikit-learn", "weedz")
                },
            },
            "limitations": [
                "Survey-point classification, not pixel segmentation or infestation polygons.",
                "One Montana site and species; New Zealand transfer is untested.",
                "Threshold chosen on validation only; scores are not calibrated probabilities.",
                "False alarms per hectare cannot be estimated from sampled survey points.",
            ],
        },
    )
    return metrics
