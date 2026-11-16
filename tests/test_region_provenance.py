"""An unlisted transitive validator change must alter reproducibility evidence."""

from weedz.region_evaluation import provenance


def test_source_tree_digest_tracks_nested_validation_modules(tmp_path, monkeypatch):
    package = tmp_path / "weedz"
    evaluator = package / "region_evaluation"
    evaluator.mkdir(parents=True)
    entry = evaluator / "provenance.py"
    entry.write_text("# evaluator\n")
    for relative in (
        "contract.py",
        "contract_versions.py",
        "review_values.py",
        "manifest.py",
        "classification/batch.py",
        "classification/regions.py",
        "segmentation/ingress.py",
    ):
        path = package / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# stable dependency\n")
    dependency = package / "consent.py"
    dependency.write_text("POLICY = 1\n")
    monkeypatch.setattr(provenance, "__file__", str(entry))
    first = provenance.evaluator_provenance()
    dependency.write_text("POLICY = 2\n")
    changed = provenance.evaluator_provenance()
    assert "consent.py" in first["module_sha256"]
    assert first["source_tree_sha256"] != changed["source_tree_sha256"]
    assert (
        first["module_sha256"]["region_evaluation/provenance.py"]
        == changed["module_sha256"]["region_evaluation/provenance.py"]
    )
