"""Resource and ownership boundaries for closed human revision packages."""

import os

import pytest
from test_human_import_apply import claims, sample
from test_human_import_pipeline import inputs

from weedz.annotation.import_apply import apply_claims
from weedz.annotation.import_pipeline import import_reviews
from weedz.contract import Annotation, revise_sample


def test_entire_package_is_private_under_common_umask(tmp_path):
    request, _, _ = inputs(tmp_path)
    previous = os.umask(0o022)
    try:
        output = tmp_path / "private-import"
        import_reviews(request, output)
    finally:
        os.umask(previous)
    assert output.stat().st_mode & 0o777 == 0o700


def test_source_prefix_is_not_proof_of_human_claim_ownership():
    record = claims().record
    original = Annotation(
        id=f"{record.key}:region:source",
        supervision="box",
        taxon="Ulex europaeus",
        label="present",
        box=(0, 0, 10, 10),
        origin="source",
    )
    source = revise_sample(sample(), annotations=[original])
    first, _ = apply_claims(source, claims(), {}, set())
    revised, _ = apply_claims(first, claims("2026-11-16T02:00:00Z"), {}, set())
    assert revised.annotations == (original,)


def test_output_is_refused_before_it_exceeds_replay_budget(tmp_path, monkeypatch):
    import weedz.annotation.import_package as package

    request, _, _ = inputs(tmp_path)
    original_size = sum(p.stat().st_size for p in request.package.rglob("*") if p.is_file())
    monkeypatch.setattr(package, "MAX_PACKAGE_BYTES", original_size + 100)
    output = tmp_path / "too-large"
    with pytest.raises(ValueError, match="resource cap"):
        import_reviews(request, output)
    assert not output.exists()


def test_oversized_export_is_refused_before_json_decode(tmp_path, monkeypatch):
    import weedz.annotation.import_pipeline as pipeline

    request, _, _ = inputs(tmp_path)
    monkeypatch.setattr(pipeline, "MAX_EXPORT_BYTES", 10, raising=False)
    with pytest.raises(ValueError, match="oversized"):
        import_reviews(request, tmp_path / "oversized")


def test_retraction_preserves_unrelated_source_prefix():
    from dataclasses import replace

    from weedz.annotation.import_retractions import retract

    record = claims().record
    original = Annotation(
        id=f"{record.key}:region:source",
        supervision="box",
        taxon="Ulex europaeus",
        label="present",
        box=(0, 0, 10, 10),
        origin="source",
    )
    first, _ = apply_claims(revise_sample(sample(), annotations=[original]), claims(), {}, set())
    cancelled = replace(
        record,
        revision="cancelled",
        sha256="f" * 64,
        recorded_at="2026-11-16T03:00:00Z",
        cancelled=True,
    )
    assert retract(first, cancelled, {}).annotations == (original,)


def test_generated_coverage_collision_is_refused_without_removing_source():
    from weedz.contract import Completeness

    record = claims().record
    original = Completeness(
        id=f"{record.key}:completeness",
        media_sha256="a" * 64,
        task="detection",
        taxa=("Ulex europaeus",),
        status="unknown",
        origin="source",
    )
    with pytest.raises(ValueError, match="collides"):
        apply_claims(revise_sample(sample(), completeness=[original]), claims(), {}, set())


def test_output_file_count_matches_reader_cap(tmp_path, monkeypatch):
    import weedz.annotation.import_package as package

    request, _, _ = inputs(tmp_path)
    count = len(__import__("json").loads((request.package / "manifest.json").read_bytes())["files"])
    monkeypatch.setattr(package, "MAX_FILES", count)
    with pytest.raises(ValueError, match="resource cap"):
        import_reviews(request, tmp_path / "too-many-files")


def test_reviewed_import_cannot_be_reused_as_fresh_source_under_new_accounts(tmp_path):
    import hashlib
    from dataclasses import replace

    request, _, _ = inputs(tmp_path)
    reviewed = tmp_path / "reviewed"
    import_reviews(request, reviewed)
    forged = replace(
        request,
        package=reviewed,
        package_sha256=hashlib.sha256((reviewed / "manifest.json").read_bytes()).hexdigest(),
        namespace="different-project-alias",
    )
    output = tmp_path / "duplicated"
    with pytest.raises(ValueError, match="fresh source"):
        import_reviews(forged, output)
    assert not output.exists()


@pytest.mark.parametrize("name", ["tasks.json", "private/provenance.json"])
def test_structural_package_json_is_bounded_before_decode(tmp_path, monkeypatch, name):
    import weedz.annotation.import_package as package

    request, _, _ = inputs(tmp_path)
    monkeypatch.setattr(package, "MAX_STRUCTURE_BYTES", 10, raising=False)
    # Both structural files are independently subject to the limit, not only exports.
    other = "private/provenance.json" if name == "tasks.json" else "tasks.json"
    original = package.pinned_bytes

    def limit_selected(path, expected, maximum=package.MAX_BYTES):
        if str(path).endswith(other):
            maximum = package.MAX_BYTES
        return original(path, expected, maximum)

    monkeypatch.setattr(package, "pinned_bytes", limit_selected)
    output = tmp_path / "oversized-structure"
    with pytest.raises(ValueError, match="oversized"):
        import_reviews(request, output)
    assert not output.exists()


def test_output_provenance_must_fit_the_next_structural_decode_cap(tmp_path, monkeypatch):
    import weedz.annotation.import_package as package

    request, _, _ = inputs(tmp_path)
    initial = max((request.package / name).stat().st_size for name in package.STRUCTURAL_FILES)
    monkeypatch.setattr(package, "MAX_STRUCTURE_BYTES", initial + 100)
    output = tmp_path / "unreplayable-structure"
    with pytest.raises(ValueError, match="resource cap"):
        import_reviews(request, output)
    assert not output.exists()
