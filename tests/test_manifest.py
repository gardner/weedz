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
    box = annotation(id="a2", supervision="box", box=[1, 2, 30, 40], origin="reviewer")
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
