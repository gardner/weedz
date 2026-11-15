"""A short music take must not quietly become a partly silent soundtrack."""

import importlib.util
import wave
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "demo_mix", Path(__file__).parents[1] / "tools/demo-video/mix_demo.py"
)
assert spec and spec.loader
mix = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mix)


def test_short_music_is_rejected_before_the_movie_is_written(tmp_path: Path) -> None:
    source = tmp_path / "short.wav"
    with wave.open(str(source), "wb") as output:
        output.setparams((2, 2, 24000, 0, "NONE", "not compressed"))
        output.writeframes(bytes(24000 * 4))
    with pytest.raises(ValueError, match="180 seconds"):
        mix.check_music(source)
