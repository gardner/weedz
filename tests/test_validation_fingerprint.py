"""Cached model evidence is keyed by the pipeline code and libraries that produced it."""

from pathlib import Path

from weedz.validation.fingerprint import imported_sources, pipeline_fingerprint


def _write(root: Path, text: str) -> Path:
    (root / "stage.py").write_text(text)
    return Path("stage.py")


def test_editing_pipeline_code_changes_the_fingerprint(tmp_path: Path):
    source = _write(tmp_path, "THRESHOLD = 0.5\n")
    before = pipeline_fingerprint([source], ["pillow"], "cpu", root=tmp_path)
    assert before == pipeline_fingerprint([source], ["pillow"], "cpu", root=tmp_path)
    _write(tmp_path, "THRESHOLD = 0.4\n")
    assert pipeline_fingerprint([source], ["pillow"], "cpu", root=tmp_path) != before


def test_settings_and_libraries_change_the_fingerprint(tmp_path: Path):
    source = _write(tmp_path, "pass\n")
    base = pipeline_fingerprint([source], ["pillow"], "cpu", root=tmp_path)
    assert pipeline_fingerprint([source], ["pillow"], "cuda:0", root=tmp_path) != base
    assert pipeline_fingerprint([source], ["pillow", "numpy"], "cpu", root=tmp_path) != base


def test_each_adapter_key_covers_the_model_code_it_runs():
    from weedz.validation import cocostuff_models, inat2021_models, openimages

    assert Path("segmentation/sam3_image.py") in openimages.PIPELINE_SOURCES["sam3"]
    assert Path("discovery/vegetation.py") in cocostuff_models.ADAPTER_SOURCES
    assert Path("classification/bioclip.py") in inat2021_models.PIPELINE_SOURCES["bioclip"]


def test_sources_follow_weedz_imports_including_lazy_ones(tmp_path: Path):
    package = tmp_path / "weedz"
    (package / "sub").mkdir(parents=True)
    (package / "sub" / "__init__.py").write_text("")
    (package / "entry.py").write_text("import json\nfrom weedz.sub import helper\n")
    (package / "sub" / "helper.py").write_text("def f():\n    from weedz.sub.math import policy\n")
    (package / "sub" / "math.py").write_text("from weedz.entry import x\n")
    found = imported_sources(Path("entry.py"), root=package)
    assert set(found) == {
        Path("entry.py"),
        Path("sub/__init__.py"),
        Path("sub/helper.py"),
        Path("sub/math.py"),
    }


def test_the_inat_stages_cover_the_fp32_policy():
    from weedz.validation.inat2021_models import PIPELINE_SOURCES

    for sources in PIPELINE_SOURCES.values():
        assert Path("classification/precision.py") in sources
        assert Path("species_aggregation.py") in sources


def test_importing_from_the_package_root_follows_its_submodules(tmp_path: Path):
    package = tmp_path / "weedz"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "entry.py").write_text("import weedz\nfrom weedz import tokens\n")
    (package / "tokens.py").write_text("")
    found = imported_sources(Path("entry.py"), root=package)
    assert set(found) == {Path("entry.py"), Path("__init__.py"), Path("tokens.py")}
