"""Closed manifests bind exact canonical pixels before a GPU or publisher can run."""

import hashlib
import json

import pytest
from PIL import Image

from weedz.batches.storage import validate_closed_batch
from weedz.contract import Media, Rights, Sample
from weedz.manifest import write_manifest


def reference(path, root):
    return {
        "path": str(path.relative_to(root)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


@pytest.fixture
def batch(tmp_path):
    folder = tmp_path / "batch"
    folder.mkdir()
    image = folder / "pixels.png"
    Image.new("RGB", (6, 4), "green").save(image)
    sample = Sample(
        id="deepweeds:source.jpg",
        source="deepweeds",
        source_id="source.jpg",
        snapshot="pinned",
        rights=Rights(
            media_license="CC-BY-4.0",
            metadata_license="CC-BY-4.0",
            attribution="Source author",
            license_source="https://example.test/source",
        ),
        media=Media(
            uri=str(image),
            sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
            width=6,
            height=4,
            format="PNG",
        ),
        tasks=frozenset({"inference"}),
    )
    manifest = folder / "samples.jsonl"
    sha = write_manifest(manifest, [sample])
    ready = folder / "ready.json"
    ready.write_text(json.dumps({"schema": 1, "count": 1, "samples_sha256": sha}))
    return tmp_path, manifest, ready, image


def test_exact_closed_batch_validates_without_changing_inputs(batch):
    root, manifest, ready, image = batch
    before = {p: p.read_bytes() for p in (manifest, ready, image)}
    value = validate_closed_batch(root, reference(manifest, root), reference(ready, root))
    assert len(value.samples) == 1
    assert value.samples[0].id == "deepweeds:source.jpg"
    assert all(path.read_bytes() == content for path, content in before.items())


def test_changed_manifest_cannot_reuse_closed_readiness(batch):
    root, manifest, ready, _ = batch
    manifest.write_bytes(manifest.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="readiness"):
        validate_closed_batch(root, reference(manifest, root), reference(ready, root))


def test_changed_pixels_refused_even_with_valid_manifest_hash(batch):
    root, manifest, ready, image = batch
    Image.new("RGB", (6, 4), "red").save(image)
    with pytest.raises(ValueError, match="image checksum"):
        validate_closed_batch(root, reference(manifest, root), reference(ready, root))


def test_readiness_count_must_match_actual_samples(batch):
    root, manifest, ready, _ = batch
    document = json.loads(ready.read_text())
    document["count"] = 2
    ready.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="count"):
        validate_closed_batch(root, reference(manifest, root), reference(ready, root))


def test_reference_hash_cannot_be_replaced_by_current_file_hash(batch):
    root, manifest, ready, _ = batch
    pinned = reference(manifest, root)
    manifest.write_bytes(manifest.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="checksum"):
        validate_closed_batch(root, pinned, reference(ready, root))


def test_late_png_metadata_cannot_enter_a_claimed_metadata_free_batch(batch):
    import struct
    import zlib

    root, manifest, ready, image = batch
    raw = image.read_bytes()
    content = b"private-coordinate\0secret"
    kind = b"tEXt"
    chunk = (
        struct.pack(">I", len(content))
        + kind
        + content
        + struct.pack(">I", zlib.crc32(kind + content) & 0xFFFFFFFF)
    )
    image.write_bytes(raw[:-12] + chunk + raw[-12:])
    sample = Sample.model_validate_json(manifest.read_text())
    sample = sample.model_copy(
        update={
            "media": sample.media.model_copy(
                update={
                    "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
                }
            )
        }
    )
    sha = write_manifest(manifest, [sample])
    ready.write_text(json.dumps({"schema": 1, "count": 1, "samples_sha256": sha}))
    with pytest.raises(ValueError, match="metadata-free"):
        validate_closed_batch(root, reference(manifest, root), reference(ready, root))
