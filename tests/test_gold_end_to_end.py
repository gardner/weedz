"""Synthetic offline dry run: these submissions are fixtures, never real human reviews."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image
from test_gold_release import materialize

from weedz.annotation.gold_config import gold_config
from weedz.annotation.import_pipeline import ImportInputs, import_reviews
from weedz.annotation.samples import export_samples
from weedz.contract import Sample, revise_sample
from weedz.manifest import read_manifest, write_manifest
from weedz.release import ReleaseSpec, read_release, write_release
from weedz.rights_profiles import NONCOMMERCIAL_PROFILE

TAXA = ("Ulex europaeus", "Austroderia toetoe")
WHEN = "2026-11-16T01:00:00Z"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_samples(root: Path) -> list[Sample]:
    samples = materialize(root)
    fourth = root / "images/4.png"
    Image.new("RGB", (40, 30), "yellow").save(fourth)
    samples.append(
        revise_sample(
            samples[0],
            id="test:4",
            source_id="4",
            media=samples[0].media.model_copy(
                update={"uri": "images/4.png", "sha256": sha(fourth)}
            ),
            completeness=(),
            review_history=(),
        )
    )
    return [
        revise_sample(
            sample,
            annotations=(),
            completeness=(),
            review_history=(),
            groups=sample.groups | {"encounter": "encounter:" + sample.groups["site"]},
            rights=sample.rights.model_copy(update={"metadata_license": "cc-by-nc-4.0"}),
        )
        for sample in samples
    ]


def results(number: int) -> list[dict]:
    rows: list[dict] = [
        dict(type="choices", from_name=name, to_name="image", value={"choices": choices})
        for name, choices in (
            ("completeness_task", ["detection"]),
            ("review_status", ["accepted"]),
            ("completeness_status", ["exhaustive"]),
            ("completeness_taxa", list(TAXA)),
        )
    ]
    if number != 2:
        rows.append(
            dict(
                id="plant",
                type="rectanglelabels",
                from_name="review_boxes",
                to_name="image",
                original_width=40,
                original_height=30,
                image_rotation=0,
                value=dict(
                    x=5, y=10, width=40, height=50, rotation=0, rectanglelabels=[TAXA[number == 3]]
                ),
            )
        )
    return rows


def dry_run(tmp_path: Path):
    source = tmp_path / "source"
    originals = source_samples(source)
    manifest = source / "samples.jsonl"
    write_manifest(manifest, originals)
    package = tmp_path / "package"
    export_samples(manifest, package, rights_profile=NONCOMMERCIAL_PROFILE)
    config = tmp_path / "gold.xml"
    config.write_text(gold_config(TAXA), encoding="utf-8")
    tasks = json.loads((package / "tasks.json").read_text())
    for number, task in enumerate(tasks, start=1):
        task.update(
            id=number,
            project=5,
            annotations=[
                dict(
                    id=100 + number,
                    task=number,
                    completed_by=11,
                    updated_by=12,
                    was_cancelled=False,
                    created_at=WHEN,
                    updated_at=WHEN,
                    result=results(number),
                )
            ],
        )
    exported = tmp_path / "synthetic-completed.json"
    exported.write_text(json.dumps(tasks))
    request = ImportInputs(
        package,
        sha(package / "manifest.json"),
        exported,
        sha(exported),
        config,
        sha(config),
        "synthetic-gold",
        5,
        TAXA,
        (),
        rights_profile=NONCOMMERCIAL_PROFILE,
    )
    return request, originals, tasks


def release_spec() -> ReleaseSpec:
    return ReleaseSpec.model_validate(
        {
            "name": "synthetic-dry-run",
            "task": "detection",
            "protocol": "Synthetic pipeline integration fixture, not actual NZ expert labels.",
            "split": {
                "kind": "explicit",
                "group_key": "site",
                "assignment": {"a": "fit", "b": "validation", "c": "test"},
            },
            "rights_profile": NONCOMMERCIAL_PROFILE,
            "review_policy": {
                "taxa": TAXA,
                "min_reviewers": 1,
                "independent": False,
                "required_groups": ["site", "observer", "encounter"],
                "reviewer_ids": ["label-studio:synthetic-gold:account:12"],
            },
        }
    )


def test_completed_review_to_frozen_release_covers_all_six_plumbing_gaps(tmp_path: Path):
    request, originals, _tasks = dry_run(tmp_path)
    imported = tmp_path / "reviewed"
    receipt = import_reviews(request, imported)
    samples = read_manifest(imported / "samples.jsonl", receipt["files"]["samples.jsonl"])
    released = write_release(
        tmp_path / "gold", samples, release_spec(), assets_root=imported, recorded_at=WHEN
    )
    record, frozen = read_release(tmp_path / "gold")
    assert record == released
    assert len(record.splits["fit"].samples) == 2
    assert len(record.splits["fit"].groups) == 1
    assert record.counts["validation"].checked_negatives == {f"taxon:{taxon}": 1 for taxon in TAXA}
    assert frozen[1].annotations == ()
    assert frozen[2].annotations[0].taxon == TAXA[1]
    assert all(sample.tasks == {"inference"} for sample in originals)
    assert all("detection" in sample.tasks for sample in frozen)
    assert all(
        sample.review_history == original.review_history
        for sample, original in zip(frozen, samples, strict=True)
    )
    assert record.metadata_licenses == ["cc-by-nc-4.0"]
    assert record.assets and len(record.assets) == 4


def test_reopened_real_revision_shape_revokes_fixture_gold_eligibility(tmp_path: Path):
    request, _originals, tasks = dry_run(tmp_path)
    first = tmp_path / "first-review"
    import_reviews(request, first)
    task = tasks[0]
    task["annotations"][0]["updated_at"] = "2026-11-16T02:00:00Z"
    next(r for r in task["annotations"][0]["result"] if r["from_name"] == "review_status")[
        "value"
    ] = {"choices": ["unreviewed"]}
    request.export.write_text(json.dumps([task]))
    revised_request = replace(request, export_sha256=sha(request.export))
    revised = tmp_path / "reopened"
    receipt = import_reviews(
        revised_request, revised, previous=first, previous_sha256=sha(first / "manifest.json")
    )
    samples = read_manifest(revised / "samples.jsonl", receipt["files"]["samples.jsonl"])
    assert len(samples[0].review_history) == 2
    with pytest.raises(ValueError, match="accepted"):
        write_release(tmp_path / "refused", samples, release_spec(), assets_root=revised)
    assert not (tmp_path / "refused").exists()


def test_a_changed_box_cannot_reuse_acceptance_of_an_older_claim_snapshot(tmp_path: Path):
    request, _originals, _tasks = dry_run(tmp_path)
    imported = tmp_path / "reviewed"
    receipt = import_reviews(request, imported)
    samples = read_manifest(imported / "samples.jsonl", receipt["files"]["samples.jsonl"])
    old = samples[0].annotations[0]
    samples[0] = revise_sample(
        samples[0], annotations=[old.model_copy(update={"box": (1, 1, 3, 3)})]
    )
    with pytest.raises(ValueError, match="history"):
        write_release(tmp_path / "refused", samples, release_spec(), assets_root=imported)
    assert not (tmp_path / "refused").exists()
