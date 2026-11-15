"""Bind native narration bytes to the declared Breeze generation receipt and passage."""

import hashlib
import json
from pathlib import Path

MODEL = "BreezeBlue/Breeze-TTS-2"
MODEL_REVISION = "3e28c5151381a722f1d8661b4118c298caa77aa4"
SOURCE_REVISION = "daa6cb2efe5471f09369229f322d20bb956cb3c3"


def verified_narration(path: Path, text: str) -> tuple[bytes, dict[str, str]]:
    try:
        raw = path.read_bytes()
        proof = json.loads(path.with_suffix(".json").read_text())
    except (OSError, ValueError) as error:
        raise ValueError("Breeze provenance is missing or malformed") from error
    expected = {
        "model": MODEL,
        "expected_model_revision": MODEL_REVISION,
        "source_revision": SOURCE_REVISION,
        "wav_sha256": hashlib.sha256(raw).hexdigest(),
        "text": text,
    }
    if not isinstance(proof, dict) or any(
        proof.get(key) != value for key, value in expected.items()
    ):
        raise ValueError("Breeze provenance does not match the selected narration bytes or passage")
    return raw, {key: value for key, value in expected.items() if key != "text"}
