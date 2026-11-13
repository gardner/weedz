import json
from pathlib import Path

import pytest

from weedz.pipeline import run_pipeline
from weedz.provenance import record_dataset, verify_dataset


def test_complete_offline_run_produces_evaluated_geospatial_artifacts(
    dataset_dir: Path, tmp_path: Path
) -> None:
    record_dataset(dataset_dir)
    output = tmp_path / "run"
    result = run_pipeline(dataset_dir, output)
    assert result["test"]["recall"] == 1
    assert result["test"]["precision"] == 1
    features = json.loads((output / "predictions.geojson").read_text())["features"]
    assert len(features) == 48
    assert features[0]["geometry"]["coordinates"] == [-114.04, 46.7]
    assert {row["properties"]["partition"] for row in features} == {"fit", "validation", "test"}
    assert all(row["geometry"]["type"] == "Point" for row in features)
    html = (output / "map.html").read_text()
    assert "data:image/png;base64," in html
    assert "survey points" in html
    assert "https://unpkg.com" not in html  # The review map works without a network.
    manifest = json.loads((output / "run.json").read_text())
    assert manifest["dataset"]["revision"]
    assert manifest["partitions"]["test"] == list(range(300, 312))
    assert (output / "model.json").exists()
    assert (output / "predictions.csv").exists()


def test_modified_images_fail_integrity_check(dataset_dir: Path) -> None:
    record_dataset(dataset_dir)
    image = next(dataset_dir.rglob("*.tif"))
    image.write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        verify_dataset(dataset_dir)


def test_rejects_output_directory_containing_existing_run(
    dataset_dir: Path, tmp_path: Path
) -> None:
    record_dataset(dataset_dir)
    output = tmp_path / "run"
    run_pipeline(dataset_dir, output)
    with pytest.raises(ValueError, match="empty"):
        run_pipeline(dataset_dir, output)


def test_run_refuses_untracked_data(dataset_dir: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="fetch"):
        run_pipeline(dataset_dir, tmp_path / "run")
