"""Import identities must bind canonical bytes and the original exported task."""

import hashlib
import io
import json

import pytest
from PIL import Image

from weedz.annotation.import_package import read_package
from weedz.contract import Sample


def package(tmp_path, dimensions=(10, 10)):
    buffer = io.BytesIO()
    Image.new("RGB", dimensions).save(buffer, format="PNG")
    pixels = buffer.getvalue()
    sample = Sample.model_validate(
        dict(
            id="fixture:one",
            source="fixture",
            source_id="one",
            snapshot="fixture-v1",
            rights={
                "media_license": "cc-by",
                "metadata_license": "cc-by",
                "attribution": "Fixture only",
                "license_source": "https://example.org",
            },
            media={
                "uri": "images/a.png",
                "sha256": hashlib.sha256(pixels).hexdigest(),
                "width": 10,
                "height": 10,
            },
            tasks=frozenset({"inference"}),
        )
    )
    key = hashlib.sha256(f"{sample.id}:{sample.media.sha256}".encode()).hexdigest()
    files = {
        "images/a.png": pixels,
        "tasks.json": json.dumps(
            [{"meta": {"external_id": key}, "data": {"image": "/data/local-files/?d=a.png"}}]
        ).encode(),
        "private/provenance.json": json.dumps(
            {"samples": [{"external_id": key, "sample": sample.model_dump(mode="json")}]}
        ).encode(),
    }
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    manifest = json.dumps(
        {"files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
    ).encode()
    (tmp_path / "manifest.json").write_bytes(manifest)
    return hashlib.sha256(manifest).hexdigest(), key


def test_package_captures_original_task_and_sample(tmp_path):
    checksum, key = package(tmp_path)
    captured = read_package(tmp_path, checksum)
    assert captured.samples[key].source_id == "one"
    (tmp_path / "images/a.png").write_bytes(b"changed")
    assert captured.files["images/a.png"].startswith(b"\x89PNG")
    with pytest.raises(ValueError, match="checksum"):
        read_package(tmp_path, checksum)


def test_package_digest_is_required(tmp_path):
    package(tmp_path)
    with pytest.raises(ValueError, match="checksum"):
        read_package(tmp_path, "0" * 64)


def test_decoded_geometry_must_match_canonical_snapshot(tmp_path):
    checksum, _ = package(tmp_path, (11, 10))
    with pytest.raises(ValueError, match="geometry"):
        read_package(tmp_path, checksum)


def test_task_image_reference_must_name_its_pinned_media(tmp_path):
    checksum, _ = package(tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_bytes())
    tasks = json.loads((tmp_path / "tasks.json").read_bytes())
    tasks[0]["data"]["image"] = "/data/local-files/?d=other.png"
    raw = json.dumps(tasks).encode()
    (tmp_path / "tasks.json").write_bytes(raw)
    manifest["files"]["tasks.json"] = hashlib.sha256(raw).hexdigest()
    encoded = json.dumps(manifest).encode()
    (tmp_path / "manifest.json").write_bytes(encoded)
    with pytest.raises(ValueError, match="image"):
        read_package(tmp_path, hashlib.sha256(encoded).hexdigest())


def test_package_total_snapshot_memory_is_bounded(tmp_path, monkeypatch):
    import weedz.annotation.import_package as module

    checksum, _ = package(tmp_path)
    monkeypatch.setattr(module, "MAX_PACKAGE_BYTES", 10, raising=False)
    with pytest.raises(ValueError, match="cap|oversized"):
        module.read_package(tmp_path, checksum)
