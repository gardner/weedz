"""Synthetic offline fixture only: no real Label Studio human submission is fabricated."""

import hashlib
import json

import pytest
from test_human_import_package import package

from weedz.annotation.gold_config import gold_config
from weedz.annotation.import_pipeline import ImportInputs, import_reviews
from weedz.manifest import read_manifest


def inputs(tmp_path):
    source = tmp_path / "original"
    source.mkdir()
    sha, key = package(source)
    config = tmp_path / "gold.xml"
    config.write_text(gold_config(("Ulex europaeus",)), encoding="utf-8")
    controls = [
        dict(type="choices", from_name=n, to_name="image", value={"choices": v})
        for n, v in (
            ("completeness_task", ["detection"]),
            ("review_status", ["accepted"]),
            ("completeness_status", ["exhaustive"]),
            ("completeness_taxa", ["Ulex europaeus"]),
        )
    ]
    task = json.loads((source / "tasks.json").read_bytes())[0]
    task.update(
        id=1,
        project=5,
        annotations=[
            dict(
                id=2,
                task=1,
                completed_by=3,
                was_cancelled=False,
                created_at="2026-11-16T01:00:00Z",
                updated_at="2026-11-16T01:00:00Z",
                result=controls,
            )
        ],
    )
    export = tmp_path / "completed.json"
    export.write_text(json.dumps([task]))
    request = ImportInputs(
        source,
        sha,
        export,
        hashlib.sha256(export.read_bytes()).hexdigest(),
        config,
        hashlib.sha256(config.read_bytes()).hexdigest(),
        "synthetic-project",
        5,
        ("Ulex europaeus",),
        (),
    )
    return request, task, key


def test_offline_import_freezes_scoped_review_and_exact_reimport(tmp_path):
    request, _, _ = inputs(tmp_path)
    output = tmp_path / "imported"
    receipt = import_reviews(request, output)
    rows = read_manifest(output / "samples.jsonl", receipt["files"]["samples.jsonl"])
    assert len(rows) == 1 and rows[0].annotations == ()
    assert rows[0].completeness[0].status == "exhaustive"
    assert rows[0].completeness[0].origin == "reviewer"
    repeated = tmp_path / "repeat"
    import_reviews(
        request,
        repeated,
        previous=output,
        previous_sha256=hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest(),
    )
    assert (repeated / "samples.jsonl").read_bytes() == (output / "samples.jsonl").read_bytes()
    assert receipt["imported_revisions"] == 1
    assert (
        output / "private/exports" / f"{request.export_sha256}.json"
    ).read_bytes() == request.export.read_bytes()


@pytest.mark.parametrize("mutation", ["image", "external_id", "project", "config"])
def test_wrong_identity_is_refused_before_output(tmp_path, mutation):
    from dataclasses import replace

    request, task, _ = inputs(tmp_path)
    if mutation == "image":
        task["data"]["image"] = "/different.png"
    elif mutation == "external_id":
        task["meta"]["external_id"] = "0" * 64
    elif mutation == "project":
        task["project"] = 6
    else:
        request.config.write_text("<View/>")
        request = replace(
            request, config_sha256=hashlib.sha256(request.config.read_bytes()).hexdigest()
        )
    request.export.write_text(json.dumps([task]))
    request = replace(
        request, export_sha256=hashlib.sha256(request.export.read_bytes()).hexdigest()
    )
    with pytest.raises(ValueError):
        import_reviews(request, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


def test_two_export_rows_cannot_reuse_one_numeric_task_id(tmp_path):
    from dataclasses import replace

    request, task, _ = inputs(tmp_path)
    duplicate = json.loads(json.dumps(task))
    request.export.write_text(json.dumps([task, duplicate]))
    request = replace(
        request, export_sha256=hashlib.sha256(request.export.read_bytes()).hexdigest()
    )
    with pytest.raises(ValueError, match="duplicate"):
        import_reviews(request, tmp_path / "refused")


def test_distinct_canonical_keys_cannot_claim_same_numeric_source_task(tmp_path):
    from dataclasses import replace

    request, task, _ = inputs(tmp_path)
    root = request.package
    provenance = json.loads((root / "private/provenance.json").read_bytes())
    second = json.loads(json.dumps(provenance["samples"][0]))
    second["sample"].update(id="fixture:two", source_id="two")
    second["external_id"] = hashlib.sha256(
        f"fixture:two:{second['sample']['media']['sha256']}".encode()
    ).hexdigest()
    provenance["samples"].append(second)
    original_tasks = json.loads((root / "tasks.json").read_bytes())
    other = json.loads(json.dumps(original_tasks[0]))
    other["meta"]["external_id"] = second["external_id"]
    original_tasks.append(other)
    manifest = json.loads((root / "manifest.json").read_bytes())
    for name, value in (("private/provenance.json", provenance), ("tasks.json", original_tasks)):
        encoded = json.dumps(value).encode()
        (root / name).write_bytes(encoded)
        manifest["files"][name] = hashlib.sha256(encoded).hexdigest()
    encoded = json.dumps(manifest).encode()
    (root / "manifest.json").write_bytes(encoded)
    duplicate = json.loads(json.dumps(task))
    duplicate["meta"]["external_id"] = second["external_id"]
    request.export.write_text(json.dumps([task, duplicate]))
    request = replace(
        request,
        package_sha256=hashlib.sha256(encoded).hexdigest(),
        export_sha256=hashlib.sha256(request.export.read_bytes()).hexdigest(),
    )
    with pytest.raises(ValueError, match="task identity"):
        import_reviews(request, tmp_path / "refused")


@pytest.mark.parametrize("kind", ["box", "mask"])
def test_actual_human_geometry_imports_without_implicit_supervision_conversion(tmp_path, kind):
    from dataclasses import replace

    import numpy as np
    from label_studio_sdk.converter.brush import mask2rle

    request, task, _ = inputs(tmp_path)
    results = task["annotations"][0]["result"]
    common = dict(
        id="region-1", to_name="image", original_width=10, original_height=10, image_rotation=0
    )
    if kind == "box":
        row = dict(
            common,
            from_name="review_boxes",
            type="rectanglelabels",
            value=dict(
                x=10, y=20, width=50, height=40, rotation=0, rectanglelabels=["Ulex europaeus"]
            ),
        )
    else:
        mask = np.zeros((10, 10), dtype=np.uint8)
        mask[2:6, 1:6] = 255
        row = dict(
            common,
            from_name="regions",
            type="brushlabels",
            value=dict(format="rle", rle=mask2rle(mask), brushlabels=["Ulex europaeus"]),
        )
        next(r for r in results if r["from_name"] == "completeness_task")["value"]["choices"] = [
            "segmentation"
        ]
    results.append(row)
    request.export.write_text(json.dumps([task]))
    request = replace(
        request, export_sha256=hashlib.sha256(request.export.read_bytes()).hexdigest()
    )
    output = tmp_path / "geometry"
    import_reviews(request, output)
    sample = read_manifest(output / "samples.jsonl")[0]
    note = sample.annotations[0]
    assert note.origin == "reviewer" and note.review == "accepted" and note.model is None
    assert note.supervision == ("box" if kind == "box" else "dense_mask")
    assert "rle" not in sample.review_history[0].model_dump_json()
    if kind == "box":
        assert note.box == (1, 2, 6, 6) and note.mask_uri is None
    else:
        assert note.box is None and note.mask_uri is not None
        assert hashlib.sha256((output / note.mask_uri).read_bytes()).hexdigest() == note.mask_sha256
    assert (output / "private").stat().st_mode & 0o777 == 0o700


def test_metadata_nc_requires_explicit_profile_and_is_preserved_on_reimport(tmp_path):
    from dataclasses import replace

    request, _, _ = inputs(tmp_path)
    root = request.package
    provenance = json.loads((root / "private/provenance.json").read_bytes())
    provenance["samples"][0]["sample"]["rights"]["metadata_license"] = "cc-by-nc"
    encoded = json.dumps(provenance).encode()
    (root / "private/provenance.json").write_bytes(encoded)
    manifest = json.loads((root / "manifest.json").read_bytes())
    manifest["files"]["private/provenance.json"] = hashlib.sha256(encoded).hexdigest()
    encoded = json.dumps(manifest).encode()
    (root / "manifest.json").write_bytes(encoded)
    request = replace(request, package_sha256=hashlib.sha256(encoded).hexdigest())
    with pytest.raises(ValueError, match="profile"):
        import_reviews(request, tmp_path / "public-refused")
    research = replace(request, rights_profile="noncommercial-cc0-by-nc")
    output = tmp_path / "research"
    receipt = import_reviews(research, output)
    assert receipt["rights_profile"] == "noncommercial-cc0-by-nc"
    assert read_manifest(output / "samples.jsonl")[0].rights.metadata_license == "cc-by-nc"
    checksum = hashlib.sha256((output / "manifest.json").read_bytes()).hexdigest()
    import_reviews(
        research, tmp_path / "research-replay", previous=output, previous_sha256=checksum
    )
    with pytest.raises(ValueError, match="profile"):
        import_reviews(request, tmp_path / "downgrade", previous=output, previous_sha256=checksum)
