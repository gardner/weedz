"""Different encodings of identical pixels are one decoded asset, not independent data."""

from io import BytesIO

from PIL import Image, PngImagePlugin

from weedz.contract import Media, Rights, Sample
from weedz.labelled.audit import audit
from weedz.labelled.publication import digest


def cohort(tmp_path, source, comment):
    root = tmp_path / source
    root.mkdir()
    image = Image.new("RGB", (3, 2), "green")
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text("comment", comment)
    out = BytesIO()
    image.save(out, format="PNG", pnginfo=metadata)
    raw = out.getvalue()
    (root / "image.png").write_bytes(raw)
    sample = Sample(
        id=f"{source}:1",
        source=source,
        source_id="1",
        snapshot="test",
        rights=Rights(
            media_license="cc0",
            metadata_license="cc0",
            attribution="Source",
            license_source="https://example.org",
        ),
        media=Media(uri="image.png", sha256=digest(raw), width=3, height=2),
        tasks=frozenset({"inference"}),
    )
    manifest = root / "samples.jsonl"
    manifest.write_text(sample.model_dump_json() + "\n")
    return manifest


def test_cross_source_decoded_duplicates_survive_different_container_metadata(tmp_path):
    a = cohort(tmp_path, "first", "one")
    b = cohort(tmp_path, "second", "two")
    report = audit((a, b))
    assert report["samples"] == 2 and report["unique_encoded_assets"] == 2
    assert report["unique_decoded_assets"] == 1
    assert report["decoded_duplicates"][0]["sample_ids"] == ["first:1", "second:1"]
