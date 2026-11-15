"""Music assembly preserves raw sources and never pads a too-short score with silence."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location(
    "music_assembly", Path(__file__).parents[1] / "tools/demo-music/assemble.py"
)
assert spec and spec.loader
assembly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assembly)


def test_linear_crossfade_keeps_peak_bounded_and_sources_unchanged() -> None:
    first = np.ones((30, 2), dtype=np.float32)
    second = np.full((30, 2), -1, dtype=np.float32)
    mixed = assembly.crossfade([first, second], 10, 1)
    assert mixed.shape == (50, 2)
    assert np.max(np.abs(mixed)) <= 1
    assert np.all(first == 1) and np.all(second == -1)
    assert np.allclose(mixed[20], 1) and np.allclose(mixed[29], -1)


def test_trim_and_fade_is_exact_without_normalization() -> None:
    raw = np.full((200, 2), 0.4, dtype=np.float32)
    result = assembly.trim_and_fade(raw, 10, 15, 1, 2)
    assert result.shape == (150, 2)
    assert np.all(result[0] == 0) and np.all(result[-1] == 0)
    assert np.allclose(result[20:120], 0.4)
    assert np.all(raw == np.float32(0.4))


def test_short_material_is_refused_instead_of_padded_or_looped() -> None:
    with pytest.raises(ValueError, match="Insufficient"):
        assembly.trim_and_fade(np.ones((50, 2), dtype=np.float32), 10, 10, 1, 1)
