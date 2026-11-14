"""Add a quiet original instrumental to the finished edit; leave raw voice files untouched."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from demo_paths import new_output  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", type=Path, required=True)
    parser.add_argument("--music", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = new_output(args.output, sidecars=(".mix.json",))
    music_gain = 0.055
    filters = (
        "[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0[voice];"
        f"[2:a]aresample=48000,volume={music_gain},apad=whole_dur=180,"
        "atrim=duration=180,afade=t=in:d=3,afade=t=out:st=174:d=6[music];"
        "[voice][music]amix=inputs=2:duration=first:normalize=0[audio]"
    )
    command = [
        str(args.ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-n",
        "-i",
        str(args.render / "picture.mp4"),
        "-i",
        str(args.render / "narration-native-24k.wav"),
        "-i",
        str(args.music),
        "-i",
        str(args.render / "weedz-demo.srt"),
        "-filter_complex",
        filters,
        "-map",
        "0:v",
        "-map",
        "[audio]",
        "-map",
        "3:s",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "256k",
        "-c:s",
        "mov_text",
        "-metadata:s:s:0",
        "language=eng",
        "-metadata",
        "title=Weedz — a second look",
        "-metadata",
        "comment=Research demo. AI-generated Breeze TTS 2 narration and "
        "MiniMax Music3 instrumental. Full source and photo credits accompany this file.",
        "-movflags",
        "+faststart",
        str(output),
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(command, check=True)
    metadata = {
        "music": str(args.music.resolve()),
        "music_sha256": hashlib.sha256(args.music.read_bytes()).hexdigest(),
        "music_gain": music_gain,
        "voice_gain": 1.0,
        "voice_processing": "No EQ, normalization, compression or speed changes. "
        "24 kHz native master retained; 48 kHz stereo delivery mix, AAC 256k.",
        "music_processing": "Gain only, three-second fade in and six-second fade out.",
        "ffmpeg_command": command,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "credits": str((args.render / "credits.json").resolve()),
    }
    output.with_suffix(".mix.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(output)


if __name__ == "__main__":
    main()
