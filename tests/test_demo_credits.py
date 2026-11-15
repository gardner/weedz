"""Distributable credits retain attribution without producer filesystem paths."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "demo_credits", Path(__file__).parents[1] / "tools/demo-video/demo_credits.py"
)
assert spec and spec.loader
credits = importlib.util.module_from_spec(spec)
spec.loader.exec_module(credits)


@pytest.mark.parametrize(
    "filename", ["/home/producer/captures/plant.png", r"C:\Users\producer\plant.png"]
)
def test_legacy_manifest_paths_are_portable_without_changing_attribution(filename: str) -> None:
    source = {
        "photos": [
            {
                "file": filename,
                "source_url": "https://example.test/photo/1",
                "creator_attribution": "Saryu Mae 前 朝琉",
                "license": "CC BY",
            }
        ]
    }
    portable = credits.portable_credits(source)
    assert portable["photos"][0] == {**source["photos"][0], "file": "plant.png"}
    assert source["photos"][0]["file"] == filename
