"""Version extensions explicitly; old v1 manifests and releases retain their bytes."""

import hashlib
import json

import pytest
from pydantic import ValidationError
from test_contract import annotation, sample
from test_release import WHEN, sites, spec

from weedz.contract import Sample, revise_sample
from weedz.manifest import manifest_bytes, read_manifest
from weedz.release import Release, build_release


def test_legacy_sample_wire_bytes_are_unchanged():
    old = Sample.model_validate(sample())
    assert old.schema_version == 1
    raw = old.model_dump_json().encode()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "6ec87900d5f277768756fd31c506c643e0441e9890978755ac733d1bf78eb296"
    )
    decoded = json.loads(raw)
    assert "completeness" not in decoded and "review_history" not in decoded
    assert "category" not in decoded["annotations"][0]
    assert "mask_sha256" not in decoded["annotations"][0]


@pytest.mark.parametrize(
    "fields",
    [
        {"annotations": [annotation(category="source-class")]},
        {
            "tasks": ["inference"],
            "annotations": [
                annotation(supervision="dense_mask", mask_uri="masks/a.png", mask_sha256="a" * 64)
            ],
        },
        {
            "completeness": [
                dict(
                    id="coverage",
                    task="detection",
                    taxa=["Ulex europaeus"],
                    status="unknown",
                    origin="source",
                    media_sha256="a" * 64,
                )
            ]
        },
        {
            "review_history": [
                dict(
                    id="e",
                    sample_id="test:1",
                    media_sha256="a" * 64,
                    origin="source",
                    actor="source",
                    action="published",
                    dimension="annotation",
                )
            ]
        },
    ],
)
def test_new_sample_extensions_select_v2_and_refuse_explicit_v1(fields):
    record = Sample.model_validate(sample(**fields))
    assert record.schema_version == 2
    with pytest.raises(ValidationError, match="version"):
        Sample.model_validate(sample(schema_version=1, **fields))


def test_validated_revision_upgrades_monotonically_without_mutating_old_record(tmp_path):
    old = Sample.model_validate(sample())
    revised = revise_sample(old, annotations=[annotation(category="source-class")])
    assert old.schema_version == 1 and revised.schema_version == 2
    cleared = revise_sample(revised, annotations=[annotation()])
    assert cleared.schema_version == 2
    with pytest.raises(ValueError, match="version"):
        revise_sample(cleared, schema_version=1)
    path = tmp_path / "mixed.jsonl"
    path.write_bytes(manifest_bytes([old, revise_sample(revised, id="test:2", source_id="2")]))
    assert [s.schema_version for s in read_manifest(path)] == [1, 2]


def test_release_derives_actual_versions_and_keeps_old_release_identity():
    old_records = sites("a", "b", "c", "d")
    old, _ = build_release(old_records, spec(), recorded_at=WHEN)
    assert old.release_format == old.contract_schema_version == 1
    assert old.id == "toy-afaed6ec0533"
    assert (
        hashlib.sha256(old.model_dump_json().encode()).hexdigest()
        == "0c1fff09e5ad48ed27c3cc904c2138ef02350aa95714ac20ba0e3e87ea305858"
    )
    records = [
        revise_sample(
            s, annotations=[{**s.annotations[0].model_dump(), "category": "source-class"}]
        )
        for s in old_records
    ]
    new, _ = build_release(records, spec(), recorded_at=WHEN)
    assert new.release_format == new.contract_schema_version == 2
    with pytest.raises(ValidationError, match="format"):
        Release.model_validate(new.model_dump() | {"release_format": 1})


def test_empty_extensions_still_emit_canonical_v1_without_new_keys():
    record = Sample.model_validate(
        sample(
            schema_version=1,
            completeness=[],
            review_history=[],
            annotations=[annotation(category=None, mask_sha256=None)],
        )
    )
    assert (
        hashlib.sha256(record.model_dump_json().encode()).hexdigest()
        == "6ec87900d5f277768756fd31c506c643e0441e9890978755ac733d1bf78eb296"
    )


def test_revision_materializes_iterators_before_selecting_version():
    old = Sample.model_validate(sample())
    updated = revise_sample(
        old, annotations=(annotation(category="source-class") for _ in range(1))
    )
    assert updated.schema_version == 2 and len(updated.annotations) == 1


def test_release_reader_checks_actual_sample_version(tmp_path):
    from weedz.release import read_release, write_release

    records = [
        revise_sample(s, annotations=[{**s.annotations[0].model_dump(), "category": "source"}])
        for s in sites("a", "b", "c", "d")
    ]
    record = write_release(tmp_path, records, spec(), recorded_at=WHEN)
    edited = Release.model_validate(record.model_dump() | {"contract_schema_version": 1})
    edited = edited.model_copy(update={"id": edited.content_id()})
    (tmp_path / "release.json").write_text(edited.model_dump_json())
    with pytest.raises(ValueError, match="actual samples"):
        read_release(tmp_path)
