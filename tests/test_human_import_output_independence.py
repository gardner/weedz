"""A new closed package cannot be published inside its immutable predecessor."""

import hashlib

import pytest
from test_human_import_pipeline import inputs

from weedz.annotation.import_pipeline import import_reviews


def test_output_must_be_independent_of_previous_package(tmp_path):
    request, _, _ = inputs(tmp_path)
    source_files = {
        str(path.relative_to(request.package)): path.read_bytes()
        for path in request.package.rglob("*")
        if path.is_file()
    }
    previous = tmp_path / "previous"
    import_reviews(request, previous)
    original_files = {
        str(path.relative_to(previous)): path.read_bytes()
        for path in previous.rglob("*")
        if path.is_file()
    }
    checksum = hashlib.sha256((previous / "manifest.json").read_bytes()).hexdigest()
    nested = previous / "nested" / "new-import"
    with pytest.raises(ValueError, match="independent"):
        import_reviews(request, nested, previous=previous, previous_sha256=checksum)
    assert not nested.parent.exists()
    assert {
        str(path.relative_to(previous)): path.read_bytes()
        for path in previous.rglob("*")
        if path.is_file()
    } == original_files
    assert {
        str(path.relative_to(request.package)): path.read_bytes()
        for path in request.package.rglob("*")
        if path.is_file()
    } == source_files
    import_reviews(request, tmp_path / "independent", previous=previous, previous_sha256=checksum)
