"""Renderer UI fonts are explicit and checked before frame composition."""

import importlib
import sys
from pathlib import Path

import pytest
from PIL import ImageFont

sys.path.insert(0, str(Path(__file__).parents[1] / "tools/demo-video"))
frames = importlib.import_module("demo_frames")


def test_configured_fonts_replace_cached_system_fonts(monkeypatch, tmp_path):
    monkeypatch.setattr(frames, "_FONT_PATHS", frames._FONT_PATHS)
    calls = []
    native = ImageFont.load_default()

    def load(path, size):
        calls.append((path, size))
        return native

    monkeypatch.setattr(frames.ImageFont, "truetype", load)
    first, second = tmp_path / "first.ttf", tmp_path / "second.ttf"
    frames.configure_fonts(first, first)
    frames.font(31)
    frames.configure_fonts(second, second)
    frames.font(31)
    assert (str(first.resolve()), 31) in calls
    assert calls[-1] == (str(second.resolve()), 31)
    frames.font.cache_clear()


def test_missing_configured_font_has_actionable_error(tmp_path):
    with pytest.raises(ValueError, match="ui-font"):
        frames.configure_fonts(tmp_path / "missing.ttf", tmp_path / "missing-bold.ttf")


def test_nondefault_font_files_can_be_loaded(tmp_path, monkeypatch):
    source = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if not source.is_file():
        pytest.skip("No local test font")
    custom = tmp_path / "custom-font.ttf"
    custom.write_bytes(source.read_bytes())
    monkeypatch.setattr(frames, "_FONT_PATHS", frames._FONT_PATHS)
    frames.configure_fonts(custom, custom)
    assert frames.font(27).getbbox("Weedz")
    frames.font.cache_clear()


def test_bad_font_refuses_render_before_output_is_created(tmp_path):
    from argparse import Namespace

    render = importlib.import_module("render_demo").render

    output = tmp_path / "unpublished"
    with pytest.raises(ValueError, match="ui-font"):
        render(Namespace(output=output, ui_font=tmp_path / "missing.ttf", ui_bold_font=None))
    assert not output.exists()
