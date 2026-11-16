"""Source annotation ambiguity, never model scores, defines primary cohort exclusion."""

from weedz.contract import Annotation, Media, Rights, Sample
from weedz.labelled.quality import select_primary


def sample(name, pixel, box):
    return Sample(
        id=f"imageweeds:{name}",
        source="imageweeds",
        source_id=name,
        snapshot="test",
        rights=Rights(
            media_license="CC-BY-4.0",
            metadata_license="CC-BY-4.0",
            attribution="Source",
            license_source="https://example.org",
        ),
        media=Media(uri=f"{name}.png", sha256="a" * 64, width=20, height=20),
        context={"decoded_pixel_sha256": pixel},
        tasks=frozenset({"detection"}),
        annotations=(
            Annotation(
                id=name,
                supervision="box",
                taxon="Bassia scoparia",
                label="present",
                box=box,
                origin="source",
            ),
        ),
    )


def test_divergent_aliases_are_all_quarantined_without_union_or_representative():
    a = sample("a", "b" * 64, (1, 1, 3, 3))
    b = sample("b", "b" * 64, (1, 1, 4, 4))
    c = sample("c", "c" * 64, (1, 1, 3, 3))
    selected, ledger = select_primary([a, b, c])
    assert selected == {"imageweeds:c"}
    assert ledger[0]["sample_ids"] == ["imageweeds:a", "imageweeds:b"]
    assert ledger[0]["annotation_variants"] == 2
    assert a.annotations[0].box == (1, 1, 3, 3) and b.annotations[0].box == (1, 1, 4, 4)


def test_even_identical_duplicate_aliases_are_not_silently_counted_twice():
    a = sample("a", "b" * 64, (1, 1, 3, 3))
    b = sample("b", "b" * 64, (1, 1, 3, 3))
    selected, ledger = select_primary([a, b])
    assert not selected and ledger[0]["annotation_variants"] == 1


def test_invalid_native_alias_quarantines_the_otherwise_valid_image():
    a = sample("a", "b" * 64, (1, 1, 3, 3))
    selected, ledger = select_primary([a], invalid_pixels={"b" * 64})
    assert not selected and ledger[0]["reason"] == "invalid_source_annotation_alias"


def test_closed_primary_preserves_all_alias_labels_and_rejects_forged_source_truth(
    tmp_path, monkeypatch
):
    from io import BytesIO

    import pytest
    from PIL import Image

    import weedz.labelled.quality as module
    from weedz.contract import revise_sample
    from weedz.labelled.native_imageweeds import NativeImage
    from weedz.labelled.pixels import pixel_sha256
    from weedz.labelled.publication import digest
    from weedz.manifest import read_manifest, write_manifest

    source = tmp_path / "source"
    source.mkdir()
    native_dir = tmp_path / "native"
    native_dir.mkdir()
    rows = []
    native = {}
    for name, colour, box in [
        ("a", "green", (1, 1, 3, 3)),
        ("b", "green", (1, 1, 4, 4)),
        ("c", "red", (1, 1, 3, 3)),
    ]:
        image = Image.new("RGB", (20, 20), colour)
        out = BytesIO()
        image.save(out, format="PNG")
        raw = out.getvalue()
        (source / f"{name}.png").write_bytes(raw)
        row = sample(name, pixel_sha256(image), box)
        row = revise_sample(
            row,
            media=Media(uri=f"{name}.png", sha256=digest(raw), width=20, height=20, format="PNG"),
            context=dict(
                row.context,
                format_profile="lossless-rgb-png",
                original_encoded_sha256="d" * 64,
                native_annotations_sha256="e" * 64,
            ),
        )
        rows.append(row)
        native[row.id] = NativeImage(
            row.id,
            "d" * 64,
            row.context["decoded_pixel_sha256"],
            "e" * 64,
            row.annotations,
            len(row.annotations),
            row.rights,
            row.snapshot,
            None,
        )
    manifest = source / "samples.jsonl"
    write_manifest(manifest, rows)
    monkeypatch.setattr(module, "inventory", lambda _: native)
    output = tmp_path / "primary"
    sha = module.prepare((manifest,), native_dir, output)
    primary = read_manifest(output / "samples.jsonl", sha)
    assert [r.id for r in primary] == ["imageweeds:c"]
    all_rows = read_manifest(output / "all-records.jsonl")
    assert len(all_rows) == 3 and [r.annotations for r in all_rows] == [r.annotations for r in rows]
    assert all_rows[0].groups["decoded_asset"] == all_rows[1].groups["decoded_asset"]
    forged = revise_sample(rows[0], annotations=(rows[2].annotations[0],))
    write_manifest(manifest, [forged, *rows[1:]])
    rejected = tmp_path / "rejected"
    with pytest.raises(ValueError, match="pinned publisher"):
        module.prepare((manifest,), native_dir, rejected)
    assert not rejected.exists()
