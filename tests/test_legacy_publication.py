"""An explicit authorization permits absent legacy metadata without rewriting a task."""

import copy
import hashlib
import json

import httpx
import pytest
from test_annotation_samples import canonical_batch as canonical_batch
from test_batch_publication import Service
from test_publication_package import exported, manifest_sha

from weedz.batches.package import validate_package
from weedz.batches.publication import publish
from weedz.segmentation.artifacts import digest


@pytest.fixture
def legacy(canonical_batch, tmp_path):
    package = validate_package(
        exported(canonical_batch, tmp_path), manifest_sha(tmp_path / "export")
    )
    task = package.tasks[0]
    current = copy.deepcopy(task)
    current["data"].pop("source_dataset")
    current["data"]["pipeline_state"] = "Historical state stays unchanged"
    current["meta"]["owner_note"] = "Preserved"
    service = Service()
    key = task["meta"]["external_id"]
    service.tasks[key] = {"id": 1, "data": current["data"], "meta": current["meta"]}
    service.predictions[1] = []
    source = json.loads((package.root / "private/provenance.json").read_text())["samples"][0]
    provenance = tmp_path / "original.json"
    provenance.write_text(json.dumps({"schema_version": 1, "photos": [source]}))
    sample = source["sample"]
    entry = {
        "task_id": 1,
        "external_id": key,
        "sample_id": sample["id"],
        "source": sample["source"],
        "source_id": sample["source_id"],
        "image_sha256": sample["media"]["sha256"],
        "data_sha256": digest(current["data"]),
        "meta_sha256": digest(current["meta"]),
    }
    document = {
        "schema": 1,
        "project_id": 1,
        "provenance": {
            "path": str(provenance),
            "sha256": hashlib.sha256(provenance.read_bytes()).hexdigest(),
        },
        "tasks": [entry],
    }
    return package, service, document


def authorize(tmp_path, document):
    path = tmp_path / "allowlist.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    path.chmod(0o600)
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def run(tmp_path, package, service, reference=None):
    with httpx.Client(
        base_url="http://127.0.0.1:8068", transport=httpx.MockTransport(service.handle)
    ) as client:
        return publish(
            package,
            1,
            client,
            service.index,
            tmp_path / "images",
            tmp_path / "state",
            tmp_path / "import.lock",
            legacy_allowlist=reference,
        )


def test_approved_absent_field_appends_predictions_and_preserves_complete_task(legacy, tmp_path):
    package, service, document = legacy
    reference = authorize(tmp_path, document)
    before = copy.deepcopy((service.tasks, service.annotations))
    result = run(tmp_path, package, service, reference)
    assert result["new_tasks"] == 0 and result["new_predictions"] == 1
    assert result["legacy_adoption"] == {
        "task_ids": [1],
        "allowlist_sha256": reference["sha256"],
        "provenance_sha256": document["provenance"]["sha256"],
    }
    assert (service.tasks, service.annotations) == before
    assert service.requests.count(("POST", "/api/projects/1/import/predictions")) == 1
    run(tmp_path, package, service, reference)
    assert service.requests.count(("POST", "/api/projects/1/import/predictions")) == 1


@pytest.mark.parametrize(
    "change",
    [
        "strict",
        "null",
        "empty",
        "wrong",
        "task",
        "meta",
        "data",
        "credit",
        "image",
        "external",
        "source",
        "source_id",
        "sample",
        "image_sha",
        "project",
        "provenance",
    ],
)
def test_unapproved_or_changed_identity_never_posts(legacy, tmp_path, change):
    package, service, document = legacy
    current = next(iter(service.tasks.values()))
    if change in {"null", "empty", "wrong"}:
        current["data"]["source_dataset"] = {"null": None, "empty": "", "wrong": "other"}[change]
        document["tasks"][0]["data_sha256"] = digest(current["data"])
    elif change in {"task", "meta", "data", "credit", "image", "external"}:
        mutations = {
            "task": lambda: current.update(id=2),
            "meta": lambda: current["meta"].update(unexpected="changed"),
            "data": lambda: current["data"].update(unexpected="changed"),
            "credit": lambda: current["data"].update(photo_credit="other credit"),
            "image": lambda: current["data"].update(image="/different.png"),
            "external": lambda: current["meta"].update(external_id="0" * 64),
        }
        mutations[change]()
    elif change in {"source", "source_id", "sample", "image_sha"}:
        field = {"sample": "sample_id", "image_sha": "image_sha256"}.get(change, change)
        document["tasks"][0][field] = "wrong"
    elif change == "project":
        document["project_id"] = 2
    elif change == "provenance":
        document["provenance"]["sha256"] = "0" * 64
    reference = None if change == "strict" else authorize(tmp_path, document)
    with pytest.raises(ValueError):
        run(tmp_path, package, service, reference)
    assert not any(method == "POST" for method, _ in service.requests)


def test_allowlist_digest_and_owner_private_file_are_required(legacy, tmp_path):
    package, service, document = legacy
    reference = authorize(tmp_path, document)
    reference["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        run(tmp_path, package, service, reference)
    reference = authorize(tmp_path, document)
    from pathlib import Path

    Path(reference["path"]).chmod(0o644)
    with pytest.raises(ValueError):
        run(tmp_path, package, service, reference)
    assert service.requests == []


@pytest.mark.parametrize(
    "change",
    [
        "duplicate_id",
        "duplicate_key",
        "unlisted",
        "rights",
        "source_credit",
        "provenance_changed",
        "symlink",
    ],
)
def test_authorization_cannot_expand_or_replace_original_source(legacy, tmp_path, change):
    from pathlib import Path

    package, service, document = legacy
    if change in {"duplicate_id", "duplicate_key"}:
        row = copy.deepcopy(document["tasks"][0])
        row["external_id" if change == "duplicate_id" else "task_id"] = (
            "0" * 64 if change == "duplicate_id" else 2
        )
        document["tasks"].append(row)
    elif change == "unlisted":
        document["tasks"][0]["external_id"] = "0" * 64
    elif change in {"rights", "source_credit"}:
        path = Path(document["provenance"]["path"])
        source = json.loads(path.read_text())
        rights = source["photos"][0]["sample"]["rights"]
        rights["metadata_license" if change == "rights" else "attribution"] = (
            "CC-BY-NC" if change == "rights" else "unrelated source credit"
        )
        path.write_text(json.dumps(source))
        document["provenance"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    reference = authorize(tmp_path, document)
    if change == "provenance_changed":
        Path(document["provenance"]["path"]).write_text("{}")
    if change == "symlink":
        original = Path(reference["path"])
        linked = tmp_path / "linked.json"
        linked.symlink_to(original)
        reference["path"] = str(linked)
    with pytest.raises(ValueError):
        run(tmp_path, package, service, reference)
    assert not any(method == "POST" for method, _ in service.requests)


def test_changed_task_after_image_copy_is_rechecked_before_mutation(legacy, tmp_path):
    package, service, document = legacy
    reference = authorize(tmp_path, document)
    calls = []

    def index():
        calls.append(True)
        if len(calls) == 2:
            next(iter(service.tasks.values()))["data"]["operator_change"] = "must be noticed"
        return copy.deepcopy(service.tasks)

    service.index = index
    with pytest.raises(ValueError, match="changed"):
        run(tmp_path, package, service, reference)
    assert not any(method == "POST" for method, _ in service.requests)


def test_correct_present_dataset_needs_no_compatibility_receipt(legacy, tmp_path):
    package, service, _ = legacy
    next(iter(service.tasks.values()))["data"]["source_dataset"] = package.tasks[0]["data"][
        "source_dataset"
    ]
    assert "legacy_adoption" not in run(tmp_path, package, service)


def test_allowlist_alias_cannot_hide_a_git_parent(legacy, tmp_path):
    from pathlib import Path

    package, service, document = legacy
    repository = tmp_path / "repository"
    (repository / ".git").mkdir(parents=True)
    nested = repository / "nested"
    nested.mkdir()
    reference = authorize(nested, document)
    alias = tmp_path / "alias"
    alias.symlink_to(nested, target_is_directory=True)
    reference["path"] = str(alias / Path(reference["path"]).name)
    with pytest.raises(ValueError, match="outside Git"):
        run(tmp_path, package, service, reference)
    assert not service.requests
