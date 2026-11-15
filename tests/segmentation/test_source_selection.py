"""The experiment must not read private intake or carry source coordinates forward."""

import importlib.util
import json
import sqlite3
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "segment_pilot", Path(__file__).resolve().parents[2] / "scripts/segment_pilot.py"
)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_public_selection_is_read_only_and_omits_coordinates_and_capture_date(tmp_path):
    database = tmp_path / "discovery.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE photos (run_id TEXT,id TEXT,record TEXT)")
        for index, licence in enumerate(["cc-by", "cc-by-nc", "cc0"]):
            record = dict(
                id=str(index),
                observation_id=1,
                photo_id=index,
                region="Nelson",
                cohort="incidental",
                source_url="https://www.inaturalist.org/observations/1",
                image_url="https://example.test/public.jpg",
                attribution="Public creator",
                photo_license=licence,
                observation_license="cc-by",
                observer="public",
                original_taxon="Bird",
                original_common_name="Bird",
                coordinate_status="public",
                latitude=-41.12345,
                longitude=173.12345,
                positional_accuracy_m=10,
                observed_on="2024-01-01",
            )
            db.execute(
                "INSERT INTO photos VALUES (?,?,?)", ("source", str(index), json.dumps(record))
            )
    before = database.read_bytes()
    selected = module.public_photos(tmp_path, "source", 6)
    assert [photo.id for photo in selected] == ["0", "2"]
    assert all(photo.latitude is None and photo.longitude is None for photo in selected)
    assert all(
        photo.observed_on is None and photo.coordinate_status == "missing" for photo in selected
    )
    assert database.read_bytes() == before
