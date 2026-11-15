import csv
import hashlib
import io
import json
import zipfile

import pytest
from PIL import Image

from weedz.contract import Sample
from weedz.deepweeds import SourcePins, materialize


def fixture(tmp_path, names=None):
    source = tmp_path / "source"
    source.mkdir()
    names = names or ["20160928-140314-0.jpg", "20160928-140337-0.jpg"]
    archive, labels = source / "images.zip", source / "labels.csv"
    with zipfile.ZipFile(archive, "w") as zipped, labels.open("w") as stream:
        writer = csv.writer(stream)
        writer.writerow(["Filename", "Label", "Species"])
        for index, name in enumerate(names):
            pixels = Image.new("RGB", (30, 20), (index * 40, 120, 0))
            encoded = io.BytesIO()
            pixels.save(encoded, format="JPEG", exif=Image.Exif())
            zipped.writestr(name, encoded.getvalue())
            writer.writerow([name, 0, "Chinee apple"])
    pins = SourcePins(
        hashlib.sha256(archive.read_bytes()).hexdigest(),
        hashlib.sha256(labels.read_bytes()).hexdigest(),
        len(names),
    )
    return archive, labels, pins


def test_source_rights_identity_closed_batches_and_resume(tmp_path):
    archive, labels, pins = fixture(tmp_path)
    output = tmp_path / "output"
    first = materialize(archive, labels, output, limit=2, batch_size=1, pins=pins)
    samples = [
        Sample.model_validate_json(p.read_text())
        for p in sorted(output.glob("batch-*/samples.jsonl"))
    ]
    assert first["count"] == 2
    assert samples[0].id == "deepweeds:20160928-140314-0.jpg"
    assert samples[0].rights.media_license == "CC-BY-4.0"
    assert samples[0].rights.creator is None
    assert samples[0].annotations == () and samples[0].tasks == {"inference"}
    assert samples[0].original_label == "Chinee apple"
    with zipfile.ZipFile(archive) as zipped:
        assert (
            samples[0].context["source_image_sha256"]
            == hashlib.sha256(zipped.read(samples[0].source_id)).hexdigest()
        )
    before = {p: p.read_bytes() for p in output.rglob("*") if p.is_file()}
    assert materialize(archive, labels, output, limit=2, batch_size=1, pins=pins) == first
    assert before == {p: p.read_bytes() for p in before}
    for path in output.glob("batch-*/ready.json"):
        ready = json.loads(path.read_text())
        assert (
            ready["samples_sha256"]
            == hashlib.sha256(path.with_name("samples.jsonl").read_bytes()).hexdigest()
        )
    with Image.open(samples[0].media.uri) as image:
        assert image.mode == "RGB" and not image.getexif() and not image.info


@pytest.mark.parametrize(
    "name", ["../escape.jpg", "/absolute.jpg", "folder/image.jpg", "..\\escape.jpg"]
)
def test_unsafe_archive_members_refused_before_output(tmp_path, name):
    archive, labels, pins = fixture(tmp_path, [name])
    with pytest.raises(ValueError, match="filename|member"):
        materialize(archive, labels, tmp_path / "out", limit=1, pins=pins)
    assert not (tmp_path / "out").exists()


def test_pinned_bytes_and_explicit_limit_refused(tmp_path):
    archive, labels, pins = fixture(tmp_path)
    with pytest.raises(ValueError, match="limit"):
        materialize(archive, labels, tmp_path / "out", limit=3, pins=pins)
    labels.write_text(labels.read_text() + "changed")
    with pytest.raises(ValueError, match="checksum"):
        materialize(archive, labels, tmp_path / "out", limit=1, pins=pins)
    assert not (tmp_path / "out").exists()


def test_interrupted_resume_reuses_closed_batch(tmp_path, monkeypatch):
    from weedz import deepweeds

    archive, labels, pins = fixture(tmp_path)
    output = tmp_path / "out"
    original, calls = deepweeds.convert, []

    def interrupted(raw, row, target, identity):
        calls.append(row["Filename"])
        if len(calls) == 2:
            raise KeyboardInterrupt()
        return original(raw, row, target, identity)

    monkeypatch.setattr(deepweeds, "convert", interrupted)
    with pytest.raises(KeyboardInterrupt):
        materialize(archive, labels, output, limit=2, batch_size=1, pins=pins)
    assert (output / "batch-0001/ready.json").exists()
    assert not (output / "batch-0002/ready.json").exists()
    monkeypatch.setattr(deepweeds, "convert", original)
    result = materialize(archive, labels, output, limit=2, batch_size=1, pins=pins)
    assert result["count"] == 2


def test_label_archive_inventory_mismatch_refused(tmp_path):
    archive, labels, pins = fixture(tmp_path)
    labels.write_text(labels.read_text().replace("Chinee apple", "Gorse"))
    pins = SourcePins(pins.archive_sha256, hashlib.sha256(labels.read_bytes()).hexdigest(), 2)
    with pytest.raises(ValueError, match="species"):
        materialize(archive, labels, tmp_path / "out", limit=2, pins=pins)
    assert not (tmp_path / "out").exists()


def test_duplicate_source_bytes_refused_before_any_ready_batch(tmp_path):
    archive, labels, pins = fixture(tmp_path)
    with zipfile.ZipFile(archive) as zipped:
        members = zipped.namelist()
        raw = zipped.read(members[0])
    with zipfile.ZipFile(archive, "w") as zipped:
        for member in members:
            zipped.writestr(member, raw)
    pins = SourcePins(hashlib.sha256(archive.read_bytes()).hexdigest(), pins.labels_sha256, 2)
    with pytest.raises(ValueError, match="Duplicate encoded"):
        materialize(archive, labels, tmp_path / "out", limit=2, batch_size=1, pins=pins)
    assert not list((tmp_path / "out").rglob("ready.json"))


@pytest.mark.parametrize("limit,batch_size", [(0, 1), (1, 0), (1, 1001), (True, 1)])
def test_budgets_are_explicit_and_bounded(tmp_path, limit, batch_size):
    archive, labels, pins = fixture(tmp_path)
    with pytest.raises(ValueError):
        materialize(
            archive, labels, tmp_path / "out", limit=limit, batch_size=batch_size, pins=pins
        )
    assert not (tmp_path / "out").exists()


def test_changed_archive_and_mismatched_member_names_refused(tmp_path):
    archive, labels, pins = fixture(tmp_path)
    archive.write_bytes(archive.read_bytes() + b"trailing modification")
    with pytest.raises(ValueError, match="checksum"):
        materialize(archive, labels, tmp_path / "out", limit=1, pins=pins)
    with zipfile.ZipFile(archive) as zipped:
        entries = [(name, zipped.read(name)) for name in zipped.namelist()]
    with zipfile.ZipFile(archive, "w") as zipped:
        for index, (name, raw) in enumerate(entries):
            zipped.writestr("20160928-140999-0.jpg" if index == 0 else name, raw)
    pins = SourcePins(hashlib.sha256(archive.read_bytes()).hexdigest(), pins.labels_sha256, 2)
    with pytest.raises(ValueError, match="differ"):
        materialize(archive, labels, tmp_path / "out", limit=1, pins=pins)
    assert not (tmp_path / "out").exists()


def test_resume_rejects_replaced_pixels_and_changed_budget(tmp_path):
    archive, labels, pins = fixture(tmp_path)
    output = tmp_path / "out"
    materialize(archive, labels, output, limit=2, pins=pins)
    with pytest.raises(ValueError, match="differs"):
        materialize(archive, labels, output, limit=1, pins=pins)
    next(output.rglob("*.png")).write_bytes(b"replacement")
    with pytest.raises(ValueError, match="checksum"):
        materialize(archive, labels, output, limit=2, pins=pins)


def test_interrupted_partial_batch_is_resumable_without_overwriting_images(tmp_path, monkeypatch):
    from weedz import deepweeds

    archive, labels, pins = fixture(tmp_path)
    output, original = tmp_path / "out", deepweeds._publish

    def interrupt(path, raw):
        if path.name == "samples.jsonl":
            raise KeyboardInterrupt()
        original(path, raw)

    monkeypatch.setattr(deepweeds, "_publish", interrupt)
    with pytest.raises(KeyboardInterrupt):
        materialize(archive, labels, output, limit=2, pins=pins)
    images = {p: p.stat().st_ino for p in output.rglob("*.png")}
    assert len(images) == 2 and not list(output.rglob("ready.json"))
    monkeypatch.setattr(deepweeds, "_publish", original)
    materialize(archive, labels, output, limit=2, pins=pins)
    assert images == {p: p.stat().st_ino for p in images}


def test_source_namespace_and_existing_unrelated_output_are_protected(tmp_path):
    archive, labels, pins = fixture(tmp_path)
    with pytest.raises(ValueError, match="source"):
        materialize(archive, labels, archive.parent, limit=1, pins=pins)
    output = tmp_path / "unrelated"
    output.mkdir()
    (output / "keep.txt").write_text("unrelated")
    with pytest.raises(ValueError, match="unrelated"):
        materialize(archive, labels, output, limit=1, pins=pins)
    assert (output / "keep.txt").read_text() == "unrelated"


def test_upright_derivative_strips_exif_and_retains_original_checksum(tmp_path):
    archive, labels, pins = fixture(tmp_path)
    with zipfile.ZipFile(archive) as zipped:
        entries = [(name, zipped.read(name)) for name in zipped.namelist()]
    pixels = Image.new("RGB", (30, 20), "green")
    exif = Image.Exif()
    exif[274] = 6
    exif[315] = "private camera metadata"
    encoded = io.BytesIO()
    pixels.save(encoded, format="JPEG", exif=exif)
    with zipfile.ZipFile(archive, "w") as zipped:
        for index, (name, raw) in enumerate(entries):
            zipped.writestr(name, encoded.getvalue() if index == 0 else raw)
    pins = SourcePins(hashlib.sha256(archive.read_bytes()).hexdigest(), pins.labels_sha256, 2)
    output = tmp_path / "out"
    materialize(archive, labels, output, limit=1, pins=pins)
    sample = Sample.model_validate_json((output / "batch-0001/samples.jsonl").read_text())
    assert (sample.media.width, sample.media.height) == (20, 30)
    assert sample.context["source_image_sha256"] == hashlib.sha256(encoded.getvalue()).hexdigest()
    with Image.open(sample.media.uri) as normalized:
        assert normalized.size == (20, 30)
        assert not normalized.info and not normalized.getexif()
