"""Generate non-commercial demo narration with the pinned Breeze inference source."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from demo_paths import new_output  # noqa: E402
from demo_voice import MODEL_REVISION, SOURCE_REVISION  # noqa: E402

VOICE = (
    "A warm, articulate adult woman speaking clear natural English. "
    "Curious and engaging documentary narration, with a confident, "
    "measured pace and gentle warmth."
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--text-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reference-audio", type=Path)
    parser.add_argument("--reference-text-file", type=Path)
    args = parser.parse_args()
    if (args.reference_audio is None) != (args.reference_text_file is None):
        parser.error("Reference audio and its exact transcript must be provided together")
    try:
        output = new_output(args.output, sidecars=(".json",))
    except ValueError as error:
        parser.error(str(error))
    source = args.source.resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != SOURCE_REVISION:
        parser.error("Check out the documented Breeze source revision first")
    text = args.text_file.read_text().strip()
    if not text:
        parser.error("The narration text file is empty")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        os.sys.executable,
        str(source / "infer.py"),
        str(args.model.resolve()),
        "--text",
        text,
        "--instruction",
        VOICE,
        "--cfg-scale",
        "4",
        "--seed",
        str(args.seed),
        "--no-fast-all",
        "--output",
        str(output),
    ]
    if args.reference_audio is not None:
        command += [
            "--ref-audio",
            str(args.reference_audio.resolve()),
            "--ref-text",
            args.reference_text_file.read_text().strip(),
        ]
    subprocess.run(command, env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"}, check=True)
    metadata = {
        "model": "BreezeBlue/Breeze-TTS-2",
        "expected_model_revision": MODEL_REVISION,
        "source_revision": revision,
        "wav_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "text": text,
        "instruction": VOICE,
        "seed": args.seed,
        "cfg_scale": 4,
        "fast_all": False,
        "purpose": "Non-commercial Weedz project demonstration",
        "reference_audio": args.reference_audio.name if args.reference_audio else None,
        "reference_audio_sha256": (
            hashlib.sha256(args.reference_audio.read_bytes()).hexdigest()
            if args.reference_audio
            else None
        ),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("torch", "torchaudio", "qwen-tts", "transformers", "soundfile")
        },
    }
    output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
