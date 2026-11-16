"""Interrupted conversion may resume; conflicting closed assets cannot be replaced."""

from pathlib import Path

import pytest

from weedz.labelled.publication import output_namespace, publish


def test_repeated_identical_bytes_resume_but_changed_inputs_refuse(tmp_path):
    path = tmp_path / "output" / "images" / "one.png"
    publish(path, b"original")
    publish(path, b"original")
    with pytest.raises(ValueError, match="differs"):
        publish(path, b"changed")
    assert path.read_bytes() == b"original"
    assert not list(path.parent.glob("tmp*"))


def test_interrupted_publication_never_exposes_partial_target(tmp_path, monkeypatch):
    import weedz.labelled.publication as module

    target = tmp_path / "asset"
    link = module.os.link

    def interrupted(*args):
        raise InterruptedError("cancel before exclusive publication")

    monkeypatch.setattr(module.os, "link", interrupted)
    with pytest.raises(InterruptedError):
        publish(target, b"complete")
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []
    monkeypatch.setattr(module.os, "link", link)
    publish(target, b"complete")
    assert target.read_bytes() == b"complete"


def test_source_overlap_and_git_output_refused_before_creation(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    with pytest.raises(ValueError, match="independent"):
        output_namespace(source / "converted", source)
    with pytest.raises(ValueError, match="outside Git"):
        output_namespace(Path(__file__).resolve().parent / "generated", source)
    assert not (source / "converted").exists()


def test_retry_reseals_existing_ancestors_after_a_failed_directory_barrier(tmp_path, monkeypatch):
    import weedz.labelled.publication as module

    target = tmp_path / "nested" / "images" / "one.png"
    original = module.sync_directory
    failed = False

    def fail_once(path):
        nonlocal failed
        if path == target.parent and not failed:
            failed = True
            raise OSError("directory barrier interrupted")
        original(path)

    monkeypatch.setattr(module, "sync_directory", fail_once)
    with pytest.raises(OSError, match="barrier"):
        publish(target, b"complete")
    synced = []

    def observe(path):
        synced.append(path)
        original(path)

    monkeypatch.setattr(module, "sync_directory", observe)
    publish(target, b"complete")
    assert target.parent in synced and target.parent.parent in synced
