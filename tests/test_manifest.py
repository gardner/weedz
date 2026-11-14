"""A JSONL manifest holds one validated sample per line and round-trips exactly."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_contract import annotation, sample

from weedz.contract import Sample
from weedz.manifest import read_manifest, write_manifest


def samples() -> list[Sample]:
    box = annotation(
        id="a2", supervision="box", box=[1, 2, 30, 40], origin="reviewer", reviewer="Ana"
    )
    return [
        Sample.model_validate(sample()),
        Sample.model_validate(
            sample(id="test:2", source_id="2", tasks=["detection"], annotations=[box])
        ),
    ]


def test_a_manifest_round_trips_and_reports_its_sha256(tmp_path: Path) -> None:
    path = tmp_path / "samples.jsonl"
    digest = write_manifest(path, samples())
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and all(json.loads(line)["schema_version"] == 1 for line in lines)
    assert read_manifest(path, digest) == samples()


def test_unicode_line_separators_in_free_text_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "samples.jsonl"
    note = "pasted note with\x85breaks"
    record = Sample.model_validate(sample(annotations=[annotation(note=note)]))
    digest = write_manifest(path, [record])
    assert read_manifest(path, digest) == [record]


def test_an_altered_manifest_fails_its_checksum(tmp_path: Path) -> None:
    path = tmp_path / "samples.jsonl"
    digest = write_manifest(path, samples())
    path.write_text(path.read_text(encoding="utf-8").replace("Ana", "Bob"), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        read_manifest(path, digest)


def test_a_manifest_rejects_duplicate_ids_and_unknown_versions(tmp_path: Path) -> None:
    path = tmp_path / "samples.jsonl"
    with pytest.raises(ValueError, match="Duplicate"):
        write_manifest(path, [samples()[0], samples()[0]])
    line = json.dumps(sample(schema_version=2))
    path.write_text(line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 1"):
        read_manifest(path)
    path.write_text((samples()[0].model_dump_json() + "\n") * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        read_manifest(path)


def test_a_manifest_is_byte_identical_whatever_the_hash_seed() -> None:
    tasks = ["inference", "image_classification", "detection"]
    box = annotation(id="a2", supervision="box", box=[1, 2, 30, 40])
    record = sample(tasks=tasks, annotations=[annotation(), box])
    script = (
        "import sys; from weedz.contract import Sample; "
        "print(Sample.model_validate_json(sys.argv[1]).model_dump_json())"
    )
    dumps = {
        subprocess.run(
            [sys.executable, "-c", script, json.dumps(record)],
            env={"PYTHONHASHSEED": str(seed)},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for seed in range(4)
    }
    assert len(dumps) == 1
    assert json.loads(dumps.pop())["tasks"] == sorted(tasks)


def test_mapping_fields_are_written_in_sorted_order(tmp_path: Path) -> None:
    forward = Sample.model_validate(
        sample(groups={"a": "1", "b": "2"}, context={"x": "1", "y": "2"})
    )
    backward = Sample.model_validate(
        sample(groups={"b": "2", "a": "1"}, context={"y": "2", "x": "1"})
    )
    first = write_manifest(tmp_path / "first.jsonl", [forward])
    second = write_manifest(tmp_path / "second.jsonl", [backward])
    assert first == second


def test_a_stale_temporary_path_cannot_block_or_clobber_a_write(tmp_path: Path) -> None:
    path = tmp_path / "manifest.jsonl"
    (tmp_path / "manifest.jsonl.tmp").mkdir()  # another writer's leftover
    write_manifest(path, samples())
    assert len(read_manifest(path)) == len(samples())
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".manifest")]


def test_a_manifest_gets_ordinary_umask_permissions(tmp_path: Path) -> None:
    import os

    path = tmp_path / "manifest.jsonl"
    write_manifest(path, samples())
    mask = os.umask(0)
    os.umask(mask)
    assert path.stat().st_mode & 0o777 == 0o666 & ~mask


def test_a_failed_write_leaves_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(self: Path, target: Path) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", refuse)
    with pytest.raises(OSError, match="disk full"):
        write_manifest(tmp_path / "manifest.jsonl", samples())
    assert list(tmp_path.iterdir()) == []
