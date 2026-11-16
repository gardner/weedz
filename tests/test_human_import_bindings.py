"""A project task/sample binding survives subset exports, including empty human rows."""

import hashlib
import json
from dataclasses import replace

import pytest
from test_human_import_pipeline import inputs

from weedz.annotation.import_pipeline import import_reviews


def two_samples(tmp_path):
    request, first, _ = inputs(tmp_path)
    root = request.package
    provenance = json.loads((root / "private/provenance.json").read_bytes())
    second = json.loads(json.dumps(provenance["samples"][0]))
    second["sample"].update(id="fixture:two", source_id="two")
    second["external_id"] = hashlib.sha256(
        f"fixture:two:{second['sample']['media']['sha256']}".encode()
    ).hexdigest()
    provenance["samples"].append(second)
    tasks = json.loads((root / "tasks.json").read_bytes())
    tasks.append(json.loads(json.dumps(tasks[0])))
    tasks[1]["meta"]["external_id"] = second["external_id"]
    receipt = json.loads((root / "manifest.json").read_bytes())
    for name, value in (("tasks.json", tasks), ("private/provenance.json", provenance)):
        raw = json.dumps(value).encode()
        (root / name).write_bytes(raw)
        receipt["files"][name] = hashlib.sha256(raw).hexdigest()
    raw = json.dumps(receipt).encode()
    (root / "manifest.json").write_bytes(raw)
    other = json.loads(json.dumps(first))
    other.update(id=2, annotations=[])
    other["meta"]["external_id"] = second["external_id"]
    return replace(request, package_sha256=hashlib.sha256(raw).hexdigest()), first, other


def export(request, tasks):
    request.export.write_text(json.dumps(tasks), encoding="utf-8")
    return replace(request, export_sha256=hashlib.sha256(request.export.read_bytes()).hexdigest())


@pytest.mark.parametrize("mutation", ["renumber", "reuse_absent_sample_id"])
def test_subset_cannot_rebind_an_earlier_task_id(tmp_path, mutation):
    request, first, other = two_samples(tmp_path)
    first["annotations"] = []  # Binding exists even when no completed record yields history.
    original = tmp_path / "first"
    import_reviews(export(request, [first]), original)
    checksum = hashlib.sha256((original / "manifest.json").read_bytes()).hexdigest()
    if mutation == "renumber":
        first["id"] = 9
        selected = first
    else:
        other["id"] = first["id"]
        selected = other
    output = tmp_path / "rebound"
    with pytest.raises(ValueError, match="task.*binding"):
        import_reviews(
            export(request, [selected]), output, previous=original, previous_sha256=checksum
        )
    assert not output.exists()


def test_distinct_subsets_keep_a_pinned_bijection_and_can_repeat(tmp_path):
    request, first, other = two_samples(tmp_path)
    first["annotations"] = []
    original = tmp_path / "first"
    import_reviews(export(request, [first]), original)
    output = tmp_path / "second"
    receipt = import_reviews(
        export(request, [other]),
        output,
        previous=original,
        previous_sha256=hashlib.sha256((original / "manifest.json").read_bytes()).hexdigest(),
    )
    assert receipt["task_bindings"] == {
        first["meta"]["external_id"]: 1,
        other["meta"]["external_id"]: 2,
    }


def test_legacy_receipt_recovers_empty_annotation_task_binding_from_pinned_export(tmp_path):
    request, first, _other = two_samples(tmp_path)
    first["annotations"] = []
    original = tmp_path / "first"
    import_reviews(export(request, [first]), original)
    path = original / "manifest.json"
    receipt = json.loads(path.read_bytes())
    del receipt["task_bindings"]  # Prior importer format; retained files stay unchanged.
    receipt.pop("owned_export_sha256", None)
    raw = json.dumps(receipt).encode()
    path.write_bytes(raw)
    first["id"] = 9
    with pytest.raises(ValueError, match="task.*binding"):
        import_reviews(
            export(request, [first]),
            tmp_path / "rebound",
            previous=original,
            previous_sha256=hashlib.sha256(raw).hexdigest(),
        )
