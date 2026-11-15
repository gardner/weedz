"""The website film requires a closed error-free capture, not merely existing footage."""

import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools/demo-video"))


@pytest.mark.parametrize(
    "proof",
    [
        None,
        {},
        [],
        {"captureSuccess": False, "browser_errors": []},
        {"captureSuccess": True, "browser_errors": ["Uncaught application error"]},
    ],
)
def test_v3_refuses_failed_or_unclosed_pipeline_capture(tmp_path, proof):
    renderer = importlib.import_module("render_web_demo")
    if proof is not None:
        (tmp_path / "capture-manifest.json").write_text(json.dumps(proof))
    with pytest.raises(ValueError, match="Pipeline browser capture"):
        renderer.validate_pipeline_capture(tmp_path)


def test_v3_accepts_a_closed_error_free_capture_receipt(tmp_path):
    renderer = importlib.import_module("render_web_demo")
    proof = {"captureSuccess": True, "browser_errors": [], "source": {"creator": "Source credit"}}
    (tmp_path / "capture-manifest.json").write_text(json.dumps(proof))
    assert renderer.validate_pipeline_capture(tmp_path) == proof
