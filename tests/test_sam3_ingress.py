"""Larger canonical inputs require an explicitly versioned SAM3 ingress policy."""

import hashlib
import json

import pytest
from test_sam3_batch import Processor

from weedz.segmentation.sam3_batch import propose_sam3_batch
from weedz.segmentation.sam3_image import Sam3Config, Sam3Image


def test_sam3_larger_input_budget_reaches_preflight_screen_and_cached_restore(tmp_path):
    from PIL import Image
    from region_helpers import sample

    from weedz.manifest import write_manifest

    source = tmp_path / "source"
    source.mkdir()
    image = source / "image.png"
    Image.new("RGB", (32, 32)).save(image)
    image.write_bytes(image.read_bytes() + bytes(20_000_000))
    record = sample(
        media={
            "uri": "image.png",
            "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "width": 32,
            "height": 32,
        }
    )
    manifest = source / "samples.jsonl"
    write_manifest(manifest, [record])
    processor = Processor()
    processor.failed = True
    baseline = Sam3Image(processor, Sam3Config(), {"checkpoint": "test"}, tmp_path / "old-cache")
    assert baseline.identity == "680c81c2873f8e88739b30980ce178981147506aab29087e9c096e9619885030"
    assert "source_ingress" not in baseline.metadata
    with pytest.raises(ValueError, match="cap"):
        propose_sam3_batch(manifest, source, tmp_path / "refused", baseline)
    assert not processor.calls
    model = Sam3Image(
        processor,
        Sam3Config(),
        {"checkpoint": "test"},
        tmp_path / "new-cache",
        max_source_bytes=160_000_000,
    )
    first = propose_sam3_batch(manifest, source, tmp_path / "output", model)
    assert first["counts"] == {"ok": 1, "empty": 0, "partial": 0, "failed": 0}
    assert propose_sam3_batch(manifest, source, tmp_path / "output", model) == first
    assert processor.calls == ["plant", "flower"]
    assert model.identity != baseline.identity
    row = json.loads((tmp_path / "output/proposals.jsonl").read_text())
    assert row["segmentation"]["provenance"]["source_ingress"]["max_source_bytes"] == 160_000_000


@pytest.mark.parametrize("maximum", [True, 0, -1, 160_000_001, float("nan")])
def test_sam3_rejects_invalid_budget_before_cache_or_model_work(tmp_path, maximum):
    processor = Processor()
    with pytest.raises(ValueError, match="byte"):
        Sam3Image(
            processor,
            Sam3Config(),
            {"checkpoint": "test"},
            tmp_path / "cache",
            max_source_bytes=maximum,
        )
    assert processor.calls == [] and not (tmp_path / "cache").exists()
