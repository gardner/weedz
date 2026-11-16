"""New review forms enforce intake controls without rebinding archived XML."""

import hashlib
from dataclasses import replace
from xml.etree import ElementTree

import pytest
from test_human_import_decode_budget import save
from test_human_import_pipeline import inputs

from weedz.annotation.gold_config import gold_config
from weedz.annotation.import_pipeline import import_reviews


@pytest.mark.parametrize(
    ("taxa", "categories"),
    [(("Ulex europaeus",), ()), ((), ("other plant",)), (("Ulex europaeus",), ("other plant",))],
)
def test_v2_requires_one_named_scope_and_disables_rotation(taxa, categories):
    root = ElementTree.fromstring(gold_config(taxa, categories, revision=2))
    scope = root.find("./Choices[@name='completeness_scope']")
    assert scope is not None and scope.attrib["required"] == "true"
    assert [choice.attrib["value"] for choice in scope] == list(taxa + categories)
    boxes = root.find("RectangleLabels")
    image = root.find("Image")
    assert boxes is not None and boxes.attrib["canRotate"] == "false"
    assert image is not None and image.attrib["rotateControl"] == "false"


def test_legacy_configuration_bytes_and_default_are_preserved():
    raw = gold_config(("Ulex europaeus",)).encode()
    assert raw == gold_config(("Ulex europaeus",), revision=1).encode()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "f85875d50e83c65756f10b7ccbfcf659abedc89021ad65b1637e7d8681540c0e"
    )


def v2(request, task):
    for row in task["annotations"][0]["result"]:
        if row["from_name"] == "completeness_taxa":
            row["from_name"] = "completeness_scope"
    request.config.write_text(
        gold_config(request.taxa, request.categories, revision=2), encoding="utf-8"
    )
    return replace(
        save(request, task), config_sha256=hashlib.sha256(request.config.read_bytes()).hexdigest()
    )


def test_legacy_capture_then_v2_revision_replays_each_original_configuration(tmp_path):
    request, task, _ = inputs(tmp_path)
    first = tmp_path / "legacy"
    import_reviews(request, first)
    task["annotations"][0]["updated_at"] = "2026-11-16T02:00:00Z"
    current = v2(request, task)
    second = tmp_path / "v2"
    import_reviews(
        current,
        second,
        previous=first,
        previous_sha256=hashlib.sha256((first / "manifest.json").read_bytes()).hexdigest(),
    )
    third = tmp_path / "repeat"
    receipt = import_reviews(
        current,
        third,
        previous=second,
        previous_sha256=hashlib.sha256((second / "manifest.json").read_bytes()).hexdigest(),
    )
    assert receipt["imported_revisions"] == 0
    assert (second / "samples.jsonl").read_bytes() == (third / "samples.jsonl").read_bytes()


@pytest.mark.parametrize("family", [1, 2])
def test_scope_answer_family_must_match_its_pinned_configuration(tmp_path, family):
    request, task, _ = inputs(tmp_path)
    if family == 1:
        task["annotations"][0]["result"][-1]["from_name"] = "completeness_scope"
        request = save(request, task)
    else:
        request = v2(request, task)
        task["annotations"][0]["result"][-1]["from_name"] = "completeness_taxa"
        request = save(request, task)
    with pytest.raises(ValueError, match="Invalid, unknown"):
        import_reviews(request, tmp_path / "refused")


def test_v2_combined_scope_preserves_taxon_and_category_namespaces(tmp_path):
    import json

    request, task, _ = inputs(tmp_path)
    request = replace(request, categories=("other plant",))
    task["annotations"][0]["result"][-1]["value"]["choices"] = ["other plant", "Ulex europaeus"]
    current = v2(request, task)
    output = tmp_path / "combined"
    import_reviews(current, output)
    coverage = json.loads((output / "samples.jsonl").read_bytes())["completeness"][0]
    assert coverage["taxa"] == ["Ulex europaeus"]
    assert coverage["categories"] == ["other plant"]


def test_v2_cannot_mix_legacy_scope_groups_or_omit_scope(tmp_path):
    request, task, _ = inputs(tmp_path)
    current = v2(request, task)
    scope = task["annotations"][0]["result"].pop()
    with pytest.raises(ValueError, match="explicit named scope"):
        import_reviews(save(current, task), tmp_path / "missing")
    task["annotations"][0]["result"].extend([scope, {**scope, "from_name": "completeness_taxa"}])
    with pytest.raises(ValueError, match="Invalid, unknown"):
        import_reviews(save(current, task), tmp_path / "mixed")


def test_configuration_cli_explicitly_creates_new_revision_two(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "new-review.xml"
    subprocess.run(
        [
            sys.executable,
            str(root / "scripts/import_label_studio_reviews.py"),
            "config",
            "--taxon",
            "Ulex europaeus",
            "--output",
            str(output),
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert output.read_text(encoding="utf-8") == gold_config(("Ulex europaeus",), revision=2)
