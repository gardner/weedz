"""Capture decoding must distinguish full frames from EOF and failed processes."""

import importlib
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools/demo-video"))


def test_partial_pipe_reads_are_accumulated_without_repeating_a_frame():
    module = importlib.import_module("demo_decoder")

    class Fragmented(io.BytesIO):
        def read(self, count: int | None = -1) -> bytes:
            return super().read(min(count, 2) if count is not None and count >= 0 else 2)

    assert module.read_exact(Fragmented(b"abcdef"), 6) == b"abcdef"


@pytest.mark.parametrize(
    "content,code,error", [(b"abc", 0, "ended early"), (b"abcdef", 7, "exited")]
)
def test_real_decoder_eof_and_nonzero_exit_are_not_success(content, code, error):
    module = importlib.import_module("demo_decoder")
    command = [
        sys.executable,
        "-c",
        f"import sys; sys.stdout.buffer.write({content!r}); sys.exit({code})",
    ]
    decoder = module.CaptureDecoder(command, (2, 1), 1, "test capture")
    try:
        with pytest.raises(RuntimeError, match=error):
            decoder.frame()
    finally:
        decoder.close(check=False)


def test_complete_capture_checks_normal_decoder_exit():
    module = importlib.import_module("demo_decoder")
    command = [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'abcdef')"]
    decoder = module.CaptureDecoder(command, (2, 1), 1, "test capture")
    assert decoder.frame().tobytes() == b"abcdef"
    decoder.close()
