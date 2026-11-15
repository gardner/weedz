"""A short music take must not quietly become a partly silent soundtrack."""

import importlib.util
import sys
import wave
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools/demo-video"))

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


def test_replaced_final_music_cannot_inherit_assembly_provenance(tmp_path: Path) -> None:
    import hashlib
    import json

    source = tmp_path / "assembled.wav"
    with wave.open(str(source), "wb") as output:
        output.setparams((2, 2, 100, 0, "NONE", "not compressed"))
        output.writeframes(bytes(180 * 100 * 4))
    sidecar = source.with_suffix(".assembly.json")
    sidecar.write_text(json.dumps({"sha256": hashlib.sha256(source.read_bytes()).hexdigest()}))
    mix.check_music(source)
    with wave.open(str(source), "wb") as output:
        output.setparams((2, 2, 100, 0, "NONE", "not compressed"))
        output.writeframes(bytes([1, 0, 1, 0]) * (180 * 100))
    with pytest.raises(ValueError, match="assembly"):
        mix.check_music(source)


def test_encoder_uses_checked_music_snapshot_if_original_changes(
    tmp_path: Path, monkeypatch
) -> None:
    import hashlib
    import json
    import sys
    from types import SimpleNamespace

    source = tmp_path / "assembled.wav"
    with wave.open(str(source), "wb") as output:
        output.setparams((2, 2, 100, 0, "NONE", "not compressed"))
        output.writeframes(bytes(180 * 100 * 4))
    checked = source.read_bytes()
    digest = hashlib.sha256(checked).hexdigest()
    source.with_suffix(".assembly.json").write_text(json.dumps({"sha256": digest}))
    render_hashes = {}
    for name in ("picture.mp4", "narration-native-24k.wav"):
        (tmp_path / name).write_bytes(name.encode())
        render_hashes[name] = hashlib.sha256(name.encode()).hexdigest()
    (tmp_path / "sha256.json").write_text(json.dumps(render_hashes))
    movie = tmp_path / "movie.mp4"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mix",
            "--render",
            str(tmp_path),
            "--music",
            str(source),
            "--ffmpeg",
            "unused-encoder",
            "--output",
            str(movie),
        ],
    )

    def encode(command, check):
        source.write_bytes(b"replaced after preflight")
        inputs = [command[index + 1] for index, arg in enumerate(command) if arg == "-i"]
        assert Path(inputs[2]).read_bytes() == checked
        for index, name in enumerate(("picture.mp4", "narration-native-24k.wav")):
            (tmp_path / name).write_bytes(b"replaced after preflight")
            assert Path(inputs[index]).read_bytes() == name.encode()
        Path(command[-1]).write_bytes(b"test encoded output")

    monkeypatch.setattr(mix, "subprocess", SimpleNamespace(run=encode))
    mix.main()
    metadata = json.loads(movie.with_suffix(".mix.json").read_text())
    assert metadata["music_sha256"] == digest
    assert str(tmp_path) not in json.dumps(metadata)


def test_render_snapshot_requires_original_producer_checksums(tmp_path):
    import hashlib
    import json

    rendered = tmp_path / "render"
    rendered.mkdir()
    name = "picture.mp4"
    (rendered / name).write_bytes(b"original")
    (rendered / "narration-native-24k.wav").write_bytes(b"voice")
    (rendered / "sha256.json").write_text(
        json.dumps(
            {
                name: hashlib.sha256(b"original").hexdigest(),
                "narration-native-24k.wav": hashlib.sha256(b"voice").hexdigest(),
            }
        )
    )
    (rendered / name).write_bytes(b"unrelated valid movie")
    private = tmp_path / "private"
    private.mkdir()
    with pytest.raises(ValueError, match="checksum"):
        mix.snapshot_render(rendered, private)
