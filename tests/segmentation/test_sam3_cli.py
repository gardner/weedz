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
