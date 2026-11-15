"""Real mask encoding stays prediction-only; blind tasks carry no model/source labels."""

import base64
import hashlib
import io
import json
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from weedz.annotation.export import export_label_studio
from weedz.annotation.label_studio import label_config

decode_rle = pytest.importorskip("label_studio_sdk.converter.brush").decode_rle


@pytest.fixture
def public_run(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    (root / "images").mkdir(parents=True)
    image = root / "images/source.png"
    Image.new("RGB", (6, 4), (80, 120, 60)).save(image)
    rgba = np.zeros((2, 3, 4), dtype=np.uint8)
    rgba[0, 0] = (80, 255, 100, 125)
    rgba[1, 2] = (80, 255, 100, 125)
    encoded = io.BytesIO()
    Image.fromarray(rgba).save(encoded, format="PNG")
    photo = dict(
        id="inat-1-2",
        observation_id=1,
        photo_id=2,
        region="Nelson",
        cohort="incidental",
        source_url="https://www.inaturalist.org/observations/1",
        image_url="https://example.test/photo.png",
        attribution="Actual creator 前",
        photo_license="cc-by",
        observation_license="cc-by",
        observer="source-observer",
        original_taxon="Chlidonias albostriatus",
        original_common_name="Black-fronted Tern",
        coordinate_status="missing",
        observed_on="2024-12-31",
        image_path="images/source.png",
        sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
    )
    scores = dict(
        width=6,
        height=4,
        best_species="Ulex europaeus",
        margin=-0.041927,
        species=[{"name": "Ulex europaeus", "margin": -0.041927}],
        segmentation={
            "status": "ok",
            "baseline_retained": True,
            "regions": [
                {
                    "id": "region-one",
                    "box": [0, 0, 6, 4],
                    "context_box": [0, 0, 6, 4],
                    "mask_size": [3, 2],
                    "mask_png": base64.b64encode(encoded.getvalue()).decode(),
                    "mask_quality": {"predicted_iou": 0.9},
                    "views": {},
                }
            ],
        },
    )
    model = {
        "model": "imageomics/bioclip-2",
        "revision": "image-revision",
        "ranking_revision": 4,
        "proposal_experiment": {
            "model": "SAM2.1 Hiera tiny",
            "checkpoint_sha256": "7" * 64,
            "code_revision": "sam-revision",
            "transforms_revision": 1,
        },
    }
    with sqlite3.connect(root / "discovery.sqlite3") as db:
        db.execute("CREATE TABLE runs(id TEXT,status TEXT,model TEXT)")
        db.execute("CREATE TABLE photos(run_id TEXT,id TEXT,record TEXT,scores TEXT)")
        db.execute("INSERT INTO runs VALUES(?,?,?)", ("run", "completed", json.dumps(model)))
        db.execute(
            "INSERT INTO photos VALUES(?,?,?,?)",
            ("run", photo["id"], json.dumps(photo), json.dumps(scores)),
        )
    return root


def test_official_mask_roundtrip_and_prediction_truth_separation(public_run: Path, tmp_path: Path):
    output = tmp_path / "assisted"
    export_label_studio(public_run, "run", output, mode="assisted")
    task = json.loads((output / "tasks.json").read_text())[0]
    assert "annotations" not in task and "ground_truth" not in task
    assert task["data"]["image"].startswith("/data/local-files/?d=")
    assert task["data"]["image"].startswith("/data/local-files/?d=corpus/")
    assert len(task["predictions"]) == 2
    assert len({p["model_version"] for p in task["predictions"]}) == 2
    result = next(r for p in task["predictions"] for r in p["result"] if r["type"] == "brushlabels")
    assert result["value"]["brushlabels"] == ["Model-proposed region"]
    assert "score" not in task["predictions"][0] and "score" not in result
    assert (result["original_width"], result["original_height"]) == (6, 4)
    decoded = decode_rle(result["value"]["rle"]).reshape(4, 6, 4)[:, :, 3]
    low = np.array([[255, 0, 0], [0, 0, 255]], dtype=np.uint8)
    assert np.array_equal(decoded, np.repeat(np.repeat(low, 2, axis=0), 2, axis=1))
    provenance = json.loads((output / "private/provenance.json").read_text())
    record = provenance["photos"][0]
    assert record["photo"]["attribution"] == "Actual creator 前"
    assert record["scores"]["margin"] == -0.041927
    assert record["sample"]["annotations"][0]["origin"] == "model"
    assert record["sample"]["annotations"][0]["label"] == "unknown"
    with Image.open(output / record["sample"]["annotations"][0]["mask_uri"]) as saved_mask:
        assert saved_mask.size == (6, 4)


def test_blind_tasks_have_no_model_or_source_taxonomy_prelabels(public_run: Path, tmp_path: Path):
    output = tmp_path / "blind"
    export_label_studio(public_run, "run", output, mode="blind")
    task = json.loads((output / "tasks.json").read_text())[0]
    assert set(task) == {"data", "meta"}
    encoded = json.dumps(task)
    for forbidden in ["Ulex", "Chlidonias", "Tern", "inat-1-2", "SAM", "margin", "predictions"]:
        assert forbidden not in encoded
    assert not (output / "private/masks").exists()
    assert (output / "private/provenance.json").is_file()


def test_export_refuses_changed_image_before_creating_output(public_run: Path, tmp_path: Path):
    image = public_run / "images/source.png"
    Image.new("RGB", (6, 4), "red").save(image)
    output = tmp_path / "bad"
    with pytest.raises(ValueError, match="checksum"):
        export_label_studio(public_run, "run", output, mode="assisted")
    assert not output.exists()


@pytest.mark.parametrize("mode", ["assisted", "blind"])
def test_human_can_record_no_plant_without_inventing_a_mask(mode):
    config = ET.fromstring(label_config(mode))
    presence = config.find("Choices[@name='plant_presence']")
    assert presence is not None and presence.attrib["required"] == "true"
    assert {choice.attrib["value"] for choice in presence} == {
        "Plant visible",
        "No plant visible",
        "Unsure",
    }
    assert config.find("Choices[@name='watchlist_presence']") is not None
    assert config.find("Choices[@name='other_plant_presence']") is not None
    assert not any(choice.attrib.get("selected") == "true" for choice in config.iter("Choice"))


def test_local_storage_uses_a_registered_subdirectory(public_run: Path, tmp_path: Path):
    output = tmp_path / "custom-prefix"
    export_label_studio(public_run, "run", output, mode="blind", image_prefix="new-corpus")
    task = json.loads((output / "tasks.json").read_text())[0]
    relative = task["data"]["image"].split("?d=", 1)[1]
    assert relative.startswith("new-corpus/")
    assert (output / "images" / relative).is_file()


@pytest.mark.parametrize(
    "prefix",
    [
        "",
        ".",
        "..",
        "../private",
        "/absolute",
        "a/../private",
        "c:/outside",
        "C:outside",
        "folder:stream",
    ],
)
def test_image_prefix_cannot_escape_registered_storage(public_run: Path, tmp_path: Path, prefix):
    output = tmp_path / "invalid-prefix"
    with pytest.raises(ValueError, match="image prefix"):
        export_label_studio(public_run, "run", output, mode="blind", image_prefix=prefix)
    assert not output.exists()


def test_classifier_failure_does_not_erase_real_sam_predictions(public_run: Path, tmp_path: Path):
    with sqlite3.connect(public_run / "discovery.sqlite3") as db:
        scores = json.loads(db.execute("SELECT scores FROM photos").fetchone()[0])
        scores["segmentation"].update(status="failed", proposal_status="ok", view_status="failed")
        db.execute("UPDATE photos SET scores=?", (json.dumps(scores),))
    output = tmp_path / "partial-model-result"
    export_label_studio(public_run, "run", output)
    task = json.loads((output / "tasks.json").read_text())[0]
    assert sum(r["type"] == "brushlabels" for p in task["predictions"] for r in p["result"]) == 1
    evidence = task["predictions"][1]["result"][-1]["value"]["text"][0]
    assert json.loads(evidence)["view_status"] == "failed"


def test_source_database_and_image_are_not_changed(public_run: Path, tmp_path: Path):
    before = {path.name: path.read_bytes() for path in public_run.rglob("*") if path.is_file()}
    export_label_studio(public_run, "run", tmp_path / "read-only")
    after = {path.name: path.read_bytes() for path in public_run.rglob("*") if path.is_file()}
    assert after == before


@pytest.mark.parametrize("cohort,license", [("device", "cc-by"), ("incidental", "cc-by-nc")])
def test_private_or_out_of_scope_media_is_not_exported(public_run, tmp_path, cohort, license):
    with sqlite3.connect(public_run / "discovery.sqlite3") as db:
        photo = json.loads(db.execute("SELECT record FROM photos").fetchone()[0])
        photo.update(cohort=cohort, photo_license=license)
        db.execute("UPDATE photos SET record=?", (json.dumps(photo),))
    output = tmp_path / "unsupported"
    with pytest.raises(ValueError):
        export_label_studio(public_run, "run", output)
    assert not output.exists()


def test_existing_output_and_source_directory_are_preserved(public_run, tmp_path):
    output = tmp_path / "existing"
    output.mkdir()
    saved = output / "human-labels.json"
    saved.write_text("preserve human work")
    with pytest.raises(ValueError, match="existing"):
        export_label_studio(public_run, "run", output)
    assert saved.read_text() == "preserve human work"
    with pytest.raises(ValueError, match="independent"):
        export_label_studio(public_run, "run", public_run / "nested-output")
    assert not (public_run / "nested-output").exists()


def test_completed_run_rejects_late_png_metadata(public_run: Path, tmp_path: Path):
    from test_annotation_samples import late_metadata_png

    image = public_run / "images/source.png"
    encoded = late_metadata_png(image.read_bytes())
    image.write_bytes(encoded)
    with sqlite3.connect(public_run / "discovery.sqlite3") as db:
        record = json.loads(db.execute("SELECT record FROM photos").fetchone()[0])
        record["sha256"] = hashlib.sha256(encoded).hexdigest()
        db.execute("UPDATE photos SET record=?", (json.dumps(record),))
    output = tmp_path / "late-metadata-run"
    with pytest.raises(ValueError, match="metadata-free"):
        export_label_studio(public_run, "run", output)
    assert not output.exists()


def test_invalid_legacy_result_scores_are_null_not_invented_numbers(
    public_run: Path, tmp_path: Path
):
    with sqlite3.connect(public_run / "discovery.sqlite3") as db:
        scores = json.loads(db.execute("SELECT scores FROM photos").fetchone()[0])
        scores["species"][0]["margin"] = float("nan")
        db.execute("UPDATE photos SET scores=?", (json.dumps(scores),))
    output = tmp_path / "legacy-invalid-score"
    export_label_studio(public_run, "run", output)
    task = json.loads((output / "tasks.json").read_text())[0]
    text = task["predictions"][0]["result"][0]["value"]["text"][0]
    assert json.loads(text)["watchlist_comparisons"][0]["margin"] is None
    private = json.loads((output / "private/provenance.json").read_text())
    assert private["photos"][0]["scores"]["species"][0]["margin"] is None
    assert "serialized as null" in private["nonfinite_result_policy"]
    assert "annotations" not in task


@pytest.mark.parametrize("mode", ["assisted", "blind"])
def test_required_public_photo_credit_is_visible_in_each_mode(public_run, tmp_path, mode):
    output = tmp_path / f"credit-{mode}"
    export_label_studio(public_run, "run", output, mode=mode)
    task = json.loads((output / "tasks.json").read_text())[0]
    credit = task["data"]["photo_credit"]
    assert "Actual creator 前" in credit and "CC BY" in credit
    assert "https://www.inaturalist.org/observations/1" in credit
    config = ET.fromstring((output / "label-config.xml").read_text())
    display = config.find("Text[@name='photo_credit']")
    assert display is not None
    assert display.attrib["value"] == "$photo_credit"
    assert display.attrib["valueType"] == "text"
    assert display.attrib["selectionEnabled"] == "false"
    assert config.find("HyperText") is None


def test_completed_run_unicode_credit_uses_utf8_under_legacy_locale(
    public_run, tmp_path, monkeypatch
):
    from test_annotation_samples import simulate_cp1252_default

    simulate_cp1252_default(monkeypatch)
    output = tmp_path / "utf8-run"
    export_label_studio(public_run, "run", output)
    task = json.loads((output / "tasks.json").read_bytes().decode("utf-8"))[0]
    assert "Actual creator 前" in task["data"]["photo_credit"]
    private = json.loads((output / "private/provenance.json").read_bytes().decode("utf-8"))
    assert private["photos"][0]["photo"]["attribution"] == "Actual creator 前"
