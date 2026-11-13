import json
from pathlib import Path

import numpy as np
import pytest

from weedz.dataset import read_observations
from weedz.evaluation import evaluate, select_threshold
from weedz.model import fit_model, load_model, save_model


def test_threshold_meets_recall_on_validation_and_minimizes_alerts() -> None:
    assert select_threshold([0, 1, 0, 1], [0.1, 0.6, 0.7, 0.8], target_recall=1) == 0.6
    assert select_threshold([0, 1, 0, 1], [0.1, 0.6, 0.7, 0.8], target_recall=0.5) == 0.8


def test_metrics_count_misses_and_false_alarms() -> None:
    result = evaluate([1, 1, 0, 0], [0.9, 0.2, 0.8, 0.1], threshold=0.5)
    assert result["confusion"] == {"tn": 1, "fp": 1, "fn": 1, "tp": 1}
    assert result["recall"] == 0.5
    assert result["precision"] == 0.5


def test_model_roundtrip_predicts_from_pixels_without_metadata(dataset_dir: Path) -> None:
    observations = read_observations(dataset_dir)
    model = fit_model(observations[:24])
    images = [row.image_path for row in observations[24:]]
    scores = model.predict(images)
    assert all(
        (score >= 0.5) == row.label for score, row in zip(scores, observations[24:], strict=True)
    )
    path = dataset_dir / "model.json"
    save_model(model, path)
    np.testing.assert_allclose(load_model(path).predict(images), scores)


@pytest.mark.parametrize("target", [0, 1.1, float("nan")])
def test_rejects_invalid_recall_target(target: float) -> None:
    with pytest.raises(ValueError, match="recall"):
        select_threshold([0, 1], [0.1, 0.8], target_recall=target)


def test_rejects_model_with_wrong_feature_dimensions(dataset_dir: Path) -> None:
    from weedz.features import FEATURE_VERSION

    path = dataset_dir / "bad-model.json"
    path.write_text(
        json.dumps(
            {
                "format_version": 1,
                "features": FEATURE_VERSION,
                "mean": [0],
                "scale": [1],
                "coefficients": [1],
                "intercept": 0,
            }
        )
    )
    with pytest.raises(ValueError, match="dimensions"):
        load_model(path)


def test_transparent_pixels_are_not_treated_as_observed_vegetation(tmp_path: Path) -> None:
    from PIL import Image

    from weedz.features import image_features

    path = tmp_path / "nodata.tif"
    Image.new("RGBA", (39, 39), (0, 0, 0, 0)).save(path)
    with pytest.raises(ValueError, match="opaque"):
        image_features(path)
