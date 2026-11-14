"""Generate non-commercial demo narration with the pinned Breeze inference source."""

import argparse
import importlib.metadata
import json
import os
import subprocess
from pathlib import Path

MODEL_REVISION = "3e28c5151381a722f1d8661b4118c298caa77aa4"
SOURCE_REVISION = "daa6cb2efe5471f09369229f322d20bb956cb3c3"
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
    if args.output.exists():
        parser.error("Choose a new output name; existing audio is never overwritten")
    source = args.source.resolve()
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != SOURCE_REVISION:
        parser.error("Check out the documented Breeze source revision first")
    text = args.text_file.read_text().strip()
    if not text:
        parser.error("The narration text file is empty")
    args.output.parent.mkdir(parents=True, exist_ok=True)
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
        str(args.output.resolve()),
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
        "model_revision": MODEL_REVISION,
        "source_revision": revision,
        "text": text,
        "instruction": VOICE,
        "seed": args.seed,
        "cfg_scale": 4,
        "fast_all": False,
        "purpose": "Non-commercial Weedz project demonstration",
        "reference_audio": str(args.reference_audio) if args.reference_audio else None,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("torch", "torchaudio", "qwen-tts", "transformers", "soundfile")
        },
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
