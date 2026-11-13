"""Portable GeoJSON, CSV, and an offline geographic point-review document."""

import base64
import csv
import io
import json
from pathlib import Path
from typing import TypedDict

from PIL import Image

from weedz.dataset import ATTRIBUTION, Observation
from weedz.evaluation import Metrics


class Prediction(TypedDict):
    sample_id: int
    partition: str
    cluster: int
    longitude: float
    latitude: float
    truth: int
    predicted: int
    score: float
    outcome: str


def prediction(row: Observation, partition: str, score: float, threshold: float) -> Prediction:
    predicted = int(score >= threshold)
    outcome = (
        ("true_positive" if row.label else "false_positive")
        if predicted
        else ("false_negative" if row.label else "true_negative")
    )
    return {
        "sample_id": row.sample_id,
        "partition": partition,
        "cluster": row.cluster,
        "longitude": row.longitude,
        "latitude": row.latitude,
        "truth": row.label,
        "predicted": predicted,
        "score": score,
        "outcome": outcome,
    }


def write_predictions(rows: list[Prediction], output: Path) -> None:
    features = [
        {
            "type": "Feature",
            "id": row["sample_id"],
            "geometry": {"type": "Point", "coordinates": [row["longitude"], row["latitude"]]},
            "properties": row,
        }
        for row in rows
    ]
    collection = {"type": "FeatureCollection", "attribution": ATTRIBUTION, "features": features}
    (output / "predictions.geojson").write_text(
        json.dumps(collection, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    with (output / "predictions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_map(
    rows: list[Prediction], observations: list[Observation], output: Path, metrics: Metrics
) -> None:
    images = {}
    for observation in observations:
        with Image.open(observation.image_path) as source:
            buffer = io.BytesIO()
            source.convert("RGB").save(buffer, format="PNG")
        images[str(observation.sample_id)] = "data:image/png;base64," + base64.b64encode(
            buffer.getvalue()
        ).decode("ascii")
    payload = json.dumps(
        {"rows": rows, "images": images, "metrics": metrics}, allow_nan=False
    ).replace("<", "\\u003c")
    template = Path(__file__).with_name("review.html").read_text(encoding="utf-8")
    (output / "map.html").write_text(template.replace("__DATA__", payload), encoding="utf-8")
