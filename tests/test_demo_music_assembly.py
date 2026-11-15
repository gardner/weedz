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


def test_replaced_wav_cannot_reuse_music3_generation_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import argparse
    import hashlib
    import json
    import sys
    from types import SimpleNamespace

    source = tmp_path / "passage.wav"
    source.write_bytes(b"original encoded WAV")
    source.with_suffix(".json").write_text(
        json.dumps(
            {
                "model": "MiniMaxAI/MiniMax-Music3",
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        )
    )
    source.write_bytes(b"a replaced WAV from another source")
    decoded = []
    monkeypatch.setitem(
        sys.modules,
        "soundfile",
        SimpleNamespace(
            read=lambda value, **kwargs: (decoded.append(value) or np.ones((20, 2)), 10),
            write=lambda path, *args, **kwargs: Path(path).write_bytes(b"assembled output"),
        ),
    )
    output = tmp_path / "bed.wav"
    args = argparse.Namespace(
        inputs=[source], output=output, seconds=1, crossfade=0, fade_in=0, fade_out=0
    )
    with pytest.raises(ValueError, match="SHA-256"):
        assembly.assemble(args)
    assert decoded == []
    assert not output.exists()
    assert not output.with_suffix(".assembly.json").exists()


def test_assembly_decodes_the_same_encoded_bytes_it_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import argparse
    import hashlib
    import io
    import json
    import sys
    from types import SimpleNamespace

    encoded = b"verified encoded WAV"
    source = tmp_path / "passage.wav"
    source.write_bytes(encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    source.with_suffix(".json").write_text(
        json.dumps(
            {
                "model": "MiniMaxAI/MiniMax-Music3",
                "sha256": digest,
            }
        )
    )
    decoded = []
    monkeypatch.setitem(
        sys.modules,
        "soundfile",
        SimpleNamespace(
            read=lambda value, **kwargs: (decoded.append(value) or np.ones((20, 2)), 10),
            write=lambda path, *args, **kwargs: Path(path).write_bytes(b"assembled output"),
        ),
    )
    output = tmp_path / "bed.wav"
    assembly.assemble(
        argparse.Namespace(
            inputs=[source], output=output, seconds=1, crossfade=0, fade_in=0, fade_out=0
        )
    )
    assert len(decoded) == 1 and isinstance(decoded[0], io.BytesIO)
    assert decoded[0].getvalue() == encoded
    assert (
        json.loads(output.with_suffix(".assembly.json").read_text())["sources"][0]["sha256"]
        == digest
    )
