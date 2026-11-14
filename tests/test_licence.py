"""The code licence is declared once, consistently, and kept apart from source-data licences."""

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPDX = "GPL-3.0-or-later"


def test_licence_file_is_the_gnu_gpl_version_3() -> None:
    text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "GNU GENERAL PUBLIC LICENSE" in text.splitlines()[0]
    assert "Version 3, 29 June 2007" in text


def test_python_package_declares_the_licence_as_a_pep_639_expression() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["license"] == SPDX
    assert project["license-files"] == ["LICENSE"]
    assert not any(c.startswith("License ::") for c in project.get("classifiers", []))


def test_web_package_declares_the_same_licence() -> None:
    package = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
    assert package["license"] == SPDX


def test_readme_says_the_code_licence_does_not_cover_third_party_material() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Licence" in readme
    assert SPDX in readme
    assert "does not relicense" in readme
