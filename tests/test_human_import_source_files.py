"""Retained source task/configuration bytes stay immutable across human imports."""

import hashlib
import json

import pytest
from test_human_import_final_closure import repack
from test_human_import_pipeline import inputs

from weedz.annotation.import_pipeline import import_reviews


@pytest.mark.parametrize(
    ("name", "operation"),
    [
        ("tasks.json", "change"),
        ("label-config.xml", "change"),
        ("label-config.xml", "remove"),
        ("private/source-note.json", "change"),
        ("private/source-note.json", "remove"),
    ],
)
def test_previous_cannot_change_or_drop_retained_source_files(
    tmp_path, monkeypatch, name, operation
):
    request, _, _ = inputs(tmp_path)
    request = repack(
        request,
        {"label-config.xml": b"<View/>", "private/source-note.json": b'{"source":"original"}'},
    )
    previous = tmp_path / "previous"
    receipt = import_reviews(request, previous)
    original_sha = hashlib.sha256((previous / "manifest.json").read_bytes()).hexdigest()
    import_reviews(
        request, tmp_path / "unchanged-replay", previous=previous, previous_sha256=original_sha
    )
    if operation == "remove":
        (previous / name).unlink()
        del receipt["files"][name]
    else:
        if name == "tasks.json":
            tasks = json.loads((previous / name).read_bytes())
            tasks[0]["data"]["photo_credit"] = "changed source credit"
            raw = json.dumps(tasks).encode()
        else:
            raw = b"changed source metadata"
        (previous / name).write_bytes(raw)
        receipt["files"][name] = hashlib.sha256(raw).hexdigest()
    manifest = json.dumps(receipt).encode()
    (previous / "manifest.json").write_bytes(manifest)
    import weedz.annotation.import_pipeline as pipeline

    def unexpected_replay(*args, **kwargs):
        pytest.fail("Changed source files must refuse before replay")

    monkeypatch.setattr(pipeline, "_apply", unexpected_replay)
    output = tmp_path / "refused"
    with pytest.raises(ValueError, match="retained source file"):
        import_reviews(
            request, output, previous=previous, previous_sha256=hashlib.sha256(manifest).hexdigest()
        )
    assert not output.exists()
