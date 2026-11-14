"""The trail-camera assessment is reproducible from metadata alone."""

import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "assess_trailcams", Path(__file__).parents[1] / "scripts" / "assess_trailcams.py"
)
assert spec and spec.loader
assess = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assess)


def coco() -> dict:
    images = [
        {"id": "a", "location": "P1_A", "project": "P1", "datetime": "2019-05-01 10:00:00"},
        {"id": "b", "location": "P1_A", "project": "P1", "datetime": "2019-05-01 22:00:00"},
        {"id": "c", "location": "P1_B", "project": "P1", "datetime": "2020-01-02 12:30:00"},
        {"id": "d", "location": "P2_unknown", "project": "P2", "datetime": None},
    ]
    return {
        "images": images,
        "categories": [{"id": 1, "name": "mouse"}, {"id": 2, "name": "robin"}],
        "annotations": [
            {"image_id": "a", "category_id": 1},
            {"image_id": "b", "category_id": 1},
            {"image_id": "c", "category_id": 2},
            {"image_id": "d", "category_id": 1},
        ],
    }


def test_summary_counts_sites_daylight_years_and_labels() -> None:
    summary = assess.summarise(coco())
    assert summary["images"] == 4
    assert summary["projects"] == 2
    assert summary["sites"] == 3
    assert summary["unknown_site_images"] == 1
    assert summary["timestamped"] == 3
    assert summary["daylight_07_19"] == 2
    assert summary["by_year"] == {"2019": 2, "2020": 1}
    assert summary["top_labels"][0] == ["mouse", 3]
    assert summary["frames_per_site"]["max"] == 2


def test_daytime_sample_takes_one_known_site_frame_per_project() -> None:
    picks = assess.daytime_sample(coco(), per_project=1)
    assert [image["id"] for image in picks] == ["c"] or [image["id"] for image in picks] == ["a"]
    assert all(not image["location"].endswith("unknown") for image in picks)


def test_cli_writes_json(tmp_path: Path) -> None:
    source = tmp_path / "meta.json"
    source.write_text(json.dumps(coco()))
    output = tmp_path / "summary.json"
    assess.main([str(source), "--output", str(output)])
    assert json.loads(output.read_text())["images"] == 4
