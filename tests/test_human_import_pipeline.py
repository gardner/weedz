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
