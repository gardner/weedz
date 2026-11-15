import subprocess
import sys


def test_optional_sam3_help_does_not_import_training_or_model_runtime():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; "
            "sys.modules['sklearn']=None; sys.modules['sam3']=None; "
            "sys.argv=['main.py','sam3-image','--help']; from weedz.cli import main; main()",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "--checkpoint" in result.stdout


def test_failed_serialization_never_publishes_partial_evidence(tmp_path):
    import pytest

    from weedz.segmentation.sam3_cli import _publish

    output = tmp_path / "evidence.json"
    with pytest.raises(ValueError):
        _publish(output, {"regions": [], "score": float("nan")})
    assert not output.exists()
    assert list(tmp_path.iterdir()) == []


def test_publication_never_replaces_a_concurrent_result(tmp_path, monkeypatch):
    import os

    import pytest

    from weedz.segmentation.sam3_cli import _publish

    output = tmp_path / "evidence.json"
    link = os.link

    def concurrent(source, destination):
        output.write_text("original evidence")
        link(source, destination)

    monkeypatch.setattr(os, "link", concurrent)
    with pytest.raises(FileExistsError):
        _publish(output, {"regions": []})
    assert output.read_text() == "original evidence"
    assert list(tmp_path.iterdir()) == [output]
