import csv
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def dataset_dir(tmp_path: Path) -> Path:
    """Small separable imagery with independent survey groups and real metadata layout."""
    root = tmp_path / "dataset"
    columns = [
        "file_name",
        "idx",
        "label",
        "longitude",
        "latitude",
        "easting",
        "northing",
        "cluster",
    ]
    for split, clusters in (("train", (0, 1, 2)), ("test", (3,))):
        directory = root / "data" / "crop" / split
        directory.mkdir(parents=True)
        with (directory / "metadata.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for cluster in clusters:
                for offset in range(12):
                    label = "present" if offset % 2 else "absent"
                    name = f"{label}/{cluster * 100 + offset}_{cluster}.tif"
                    image_path = directory / name
                    image_path.parent.mkdir(exist_ok=True)
                    color = (210, 210, 35) if label == "present" else (20, 100, 40)
                    Image.new("RGB", (39, 39), color).save(image_path)
                    writer.writerow(
                        {
                            "file_name": name,
                            "idx": cluster * 100 + offset,
                            "label": label,
                            "longitude": -114.04 + cluster * 0.001 + offset * 0.00001,
                            "latitude": 46.7,
                            "easting": 726000 + cluster * 100 + offset * 2,
                            "northing": 5176000,
                            "cluster": cluster,
                        }
                    )
    return root
