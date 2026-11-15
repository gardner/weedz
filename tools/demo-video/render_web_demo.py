"""Render the value-first website film using actual saved pipeline evidence."""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from demo_timeline import caption_cues, load_timeline, narration_master, srt
from render_demo import encode_picture
from web_demo_frames import WebsiteFrames

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from demo_paths import new_output  # noqa: E402


def render(args: argparse.Namespace) -> None:
    output = new_output(args.output)
    required = [
        args.pipeline / name
        for name in (
            "capture-manifest.json",
            "source-reference.png",
            "original-ui.png",
            "mask-1-ui.png",
            "mask-2-ui.png",
            "classification-1-ui.png",
            "classification-2-ui.png",
            "human-review-controls.png",
            "sam21-pipeline-ui.mp4",
        )
    ] + [
        args.captures / "review-snapshot/capture-provenance.json",
        args.captures / "review-snapshot/images/460347209.png",
        args.credit_font,
    ]
    if missing := [str(p) for p in required if not p.is_file()]:
        raise ValueError("Missing actual capture evidence: " + ", ".join(missing))
    scenes = load_timeline(args.script, args.audio)
    measured = json.loads(args.transcript.read_text())
    flattened = [
        {"words": [w for segment in scene["segments"] for w in segment["words"]]}
        for scene in measured["scenes"]
    ]
    with tempfile.TemporaryDirectory(prefix="weedz-caption-") as private:
        aligned = Path(private) / "words.json"
        aligned.write_text(json.dumps(flattened))
        cues = caption_cues(scenes, aligned)
    output.mkdir(parents=True, exist_ok=False)
    narration_master(scenes, output / "narration-native-24k.wav")
    (output / "weedz-demo.srt").write_text(srt(cues))
    frames = WebsiteFrames(args.captures, args.pipeline, args.ffmpeg, args.credit_font)
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
        "24",
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
    encode_picture(command, frames, scenes, cues, 24, output)
    sources = json.loads((args.captures / "review-snapshot/capture-provenance.json").read_text())
    pipeline = json.loads((args.pipeline / "capture-manifest.json").read_text())
    credits = {
        "project": "https://github.com/gardner/weedz",
        "photography": [r for r in sources["photos"] if r["file"] == "images/460347209.png"],
        "pipeline_photo": pipeline["source"],
        "pipeline_models": {
            "segmentation": pipeline["segmentation"],
            "baseline": pipeline["baseline"],
        },
        "footage": pipeline["description"],
        "narration": {
            "model": "BreezeBlue/Breeze-TTS-2",
            "processing": "Native PCM unchanged; silence between utterances. "
            "No EQ, gain, normalization or speed changes.",
            "license": "https://huggingface.co/BreezeBlue/Breeze-TTS-2/blob/main/LICENSE",
        },
        "music": "MiniMax Music3; the final mix records its selected source and hash separately.",
        "font": "Noto Sans CJK Japanese / SIL Open Font License 1.1",
        "modifications": "Upright metadata-free source pixels, static resizing, "
        "real model mask overlays, captions and editorial composition. No pan or zoom.",
    }
    (output / "credits.json").write_text(json.dumps(credits, ensure_ascii=False, indent=2) + "\n")
    portable_scenes = [{**s, "audio": Path(s["audio"]).name} for s in scenes]
    (output / "timeline.json").write_text(json.dumps(portable_scenes, indent=2) + "\n")
    hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()
    }
    (output / "sha256.json").write_text(json.dumps(hashes, indent=2) + "\n")
    print(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--pipeline", type=Path, required=True)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--credit-font", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--script", type=Path, default=Path("docs/demo/narration-v3.json"))
    render(parser.parse_args())


if __name__ == "__main__":
    main()
