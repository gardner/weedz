"""Fast captures retain the complete interval consumed by the decoder."""

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "elapsed,minimum,remaining",
    [
        (10100, 13500, 3400),
        (13500, 13500, 0),
        (14000, 13500, 0),
        (15000, 16000, 1000),
        (16000, 16000, 0),
    ],
)
def test_capture_waits_only_for_the_missing_recording_interval(elapsed, minimum, remaining):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is unavailable")
    root = Path(__file__).parents[1]
    module = (root / "web/scripts/capture-duration.mjs").as_uri()
    subprocess.run(
        [
            node,
            "--input-type=module",
            "-e",
            f"""
import assert from 'node:assert/strict';
import {{ finishRecordingInterval }} from {module!r};
let waited = null;
globalThis.performance = {{now: () => {elapsed}}};
await finishRecordingInterval({{waitForTimeout: async (ms) => {{waited = ms;}}}}, 0, {minimum});
assert.equal(waited, {remaining});
""",
        ],
        check=True,
        capture_output=True,
    )
