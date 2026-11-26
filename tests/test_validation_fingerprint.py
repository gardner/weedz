"""Cached model evidence is keyed by the pipeline code and libraries that produced it."""

from pathlib import Path

from weedz.validation.fingerprint import SAM3_SOURCES, SEGFORMER_SOURCES, pipeline_fingerprint


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


def test_the_named_pipeline_sources_exist():
    from weedz.validation.inat2021_models import PIPELINE_SOURCES

    package = Path(__file__).resolve().parents[1] / "src" / "weedz"
    inat = [source for sources in PIPELINE_SOURCES.values() for source in sources]
    for source in (*SAM3_SOURCES, *SEGFORMER_SOURCES, *inat):
        assert (package / source).is_file(), source
