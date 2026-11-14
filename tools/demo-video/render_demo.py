"""Render the three-minute documentary without adding generated media to Git."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from demo_frames import Frames, caption, dissolve
from demo_timeline import caption_cues, load_timeline, narration_master, srt

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from demo_paths import outside_git  # noqa: E402


def render(args: argparse.Namespace) -> None:
    output = outside_git(args.output)
    if output.exists():
        raise ValueError("Choose a new output directory; renders are never overwritten")
    scenes = load_timeline(args.script, args.audio)
    cues = caption_cues(scenes, args.audio / "raw-v3-transcripts.json")
    output.mkdir(parents=True)
    narration_master(scenes, output / "narration-native-24k.wav")
    (output / "weedz-demo.srt").write_text(srt(cues))
    frames = Frames(args.captures, args.ffmpeg, args.fps, args.credit_font)
    command = [
        str(args.ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgb24",
        "-video_size",
        "1920x1080",
        "-framerate",
        str(args.fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(output / "picture.mp4"),
    ]
    encode_picture(command, frames, scenes, cues, args.fps, output)
    credits = {
        "project": "https://github.com/gardner/weedz",
        "disclosure": "Research demonstration. Actual review UI; phone widgets are prototypes. "
        "AI-generated generic voice and original instrumental. No personal library "
        "photos or live report submissions.",
        "narration": {
            "model": "BreezeBlue/Breeze-TTS-2",
            "processing": "Native PCM unchanged; "
            "silence inserted between utterances. No EQ, gain, normalization or speed "
            "changes. Final MP4 uses normal delivery encoding.",
            "license": "https://huggingface.co/BreezeBlue/Breeze-TTS-2/blob/main/LICENSE",
        },
        "music": "MiniMax Music3; see music provenance supplied with final mix",
        "photo_sources": json.loads(
            (args.captures / "review-snapshot/capture-provenance.json").read_text()
        ),
        "flutter_photo": json.loads((args.captures / "assets/attribution.json").read_text()),
        "photo_modifications": "Metadata removed, orientation corrected, resized for composition. "
        "Intro gently crops/zooms. Search-window graphic is schematic.",
        "credit_font": "Noto Sans CJK Japanese / SIL Open Font License 1.1",
        "font_source": "https://github.com/notofonts/noto-cjk",
    }
    (output / "credits.json").write_text(json.dumps(credits, ensure_ascii=False, indent=2) + "\n")
    (output / "timeline.json").write_text(json.dumps(scenes, indent=2) + "\n")
    manifest = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in output.iterdir()
        if path.is_file()
    }
    (output / "sha256.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(output)


def encode_picture(
    command: list[str], frames: Frames, scenes: list[dict], cues: list[dict], fps: int, output: Path
) -> None:
    scene_index, previous = 0, None
    canvas = frames.base("A SECOND LOOK")
    cue_index = 0
    try:
        with subprocess.Popen(command, stdin=subprocess.PIPE) as encoder:
            assert encoder.stdin is not None
            for number in range(round(scenes[-1]["end"] * fps)):
                seconds = number / fps
                if seconds >= scenes[scene_index]["end"]:
                    previous = canvas.copy()
                    scene_index += 1
                elapsed = seconds - scenes[scene_index]["start"]
                canvas = frames.render(scene_index, elapsed)
                canvas = dissolve(canvas, previous, elapsed)
                if elapsed == 1:
                    canvas.save(output / f"scene-{scene_index + 1:02}.png")
                while cue_index < len(cues) and seconds >= cues[cue_index]["end"]:
                    cue_index += 1
                if cue_index < len(cues) and cues[cue_index]["start"] <= seconds:
                    caption(canvas, cues[cue_index]["text"])
                encoder.stdin.write(canvas.tobytes())
                if number % (fps * 15) == 0:
                    print(f"Rendered {seconds:.0f} / {scenes[-1]['end']} seconds", flush=True)
            encoder.stdin.close()
            if encoder.wait() != 0:
                raise RuntimeError("Encoder failed; inspect the partial render")
    finally:
        frames.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--script", type=Path, default=Path("docs/demo/narration.json"))
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--credit-font", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fps", type=int, choices=(24, 25, 30), default=24)
    render(parser.parse_args())


if __name__ == "__main__":
    main()
