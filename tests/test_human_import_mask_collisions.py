"""Generated mask names cannot overwrite a retained closed source/prior asset."""

import hashlib
import json
from dataclasses import replace
from io import BytesIO

import numpy as np
import pytest
from label_studio_sdk.converter.brush import mask2rle
from PIL import Image
from test_human_import_decode_budget import request_with_masks, save

from weedz.annotation.import_pipeline import import_reviews
from weedz.contract import Annotation, Sample, revise_sample


def png(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def collision_inputs(tmp_path, kind, identical=False):
    request, task = request_with_masks(tmp_path)
    task["annotations"][0]["result"][-1]["value"]["rle"] = mask2rle(
        np.full((10, 10), 255, dtype=np.uint8)
    )
    normalized = png(Image.new("L", (10, 10), 255))
    uri = f"masks/{hashlib.sha256(normalized).hexdigest()}.png"
    root = request.package
    manifest = json.loads((root / "manifest.json").read_bytes())
    provenance = json.loads((root / "private/provenance.json").read_bytes())
    original = Sample.model_validate(provenance["samples"][0]["sample"])
    if kind == "media":
        retained = (root / original.media.uri).read_bytes()
        (root / original.media.uri).unlink()
        del manifest["files"][original.media.uri]
        updated = revise_sample(original, media={**original.media.model_dump(), "uri": uri})
        task["data"]["image"] = f"/data/local-files/?d={uri}"
        canonical = json.loads((root / "tasks.json").read_bytes())
        canonical[0]["data"]["image"] = task["data"]["image"]
    else:
        image = Image.new("L", (10, 10), 255)
        image.putpixel((0, 0), 0)
        retained = normalized if identical else png(image)
        note = Annotation(
            id="source-mask",
            supervision="dense_mask",
            taxon="Ulex europaeus",
            label="present",
            origin="source",
            mask_uri=uri,
            mask_sha256=hashlib.sha256(retained).hexdigest(),
        )
        updated = revise_sample(original, annotations=[note])
        canonical = json.loads((root / "tasks.json").read_bytes())
    provenance["samples"][0]["sample"] = updated.model_dump(mode="json")
    assets = {
        uri: retained,
        "tasks.json": json.dumps(canonical).encode(),
        "private/provenance.json": json.dumps(provenance).encode(),
    }
    for name, raw in assets.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        manifest["files"][name] = hashlib.sha256(raw).hexdigest()
    raw = json.dumps(manifest).encode()
    (root / "manifest.json").write_bytes(raw)
    return replace(request, package_sha256=hashlib.sha256(raw).hexdigest()), task, uri, retained


@pytest.mark.parametrize("seed", ["original", "previous"])
@pytest.mark.parametrize("kind", ["media", "mask"])
def test_conflicting_generated_mask_refuses_without_altering_retained_assets(tmp_path, seed, kind):
    request, task, uri, retained = collision_inputs(tmp_path, kind)
    prior = None
    checksum = None
    if seed == "previous":
        empty = json.loads(json.dumps(task))
        empty["annotations"] = []
        prior = tmp_path / "previous"
        import_reviews(save(request, empty), prior)
        checksum = hashlib.sha256((prior / "manifest.json").read_bytes()).hexdigest()
    output = tmp_path / "conflicting"
    with pytest.raises(ValueError, match="asset.*conflict"):
        import_reviews(save(request, task), output, previous=prior, previous_sha256=checksum)
    assert not output.exists()
    assert (request.package / uri).read_bytes() == retained
    if prior is not None:
        assert (prior / uri).read_bytes() == retained


def test_identical_retained_mask_bytes_are_reused(tmp_path):
    request, task, uri, retained = collision_inputs(tmp_path, "mask", identical=True)
    output = tmp_path / "equal-reuse"
    import_reviews(save(request, task), output)
    assert (output / uri).read_bytes() == retained
