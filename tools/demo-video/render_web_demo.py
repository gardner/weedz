"""Render the value-first website film using actual saved pipeline evidence."""

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from demo_evidence import photo_record, verified_photo_bytes
from demo_frames import configure_fonts
from demo_integrity import checked_files
from demo_timeline import caption_cues, load_timeline, narration_master, srt
from render_demo import encode_picture, validate_credit_font
from web_demo_frames import WebsiteFrames

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from demo_paths import new_output  # noqa: E402

from weedz.discovery.sharing import refuse_unadmitted, terms  # noqa: E402

PIPELINE_MEDIA = (
    "source-reference.png",
    "original-ui.png",
    "mask-1-ui.png",
    "mask-2-ui.png",
    "classification-1-ui.png",
    "classification-2-ui.png",
    "human-review-controls.png",
    "sam21-pipeline-ui.mp4",
    "model-evidence.json",
)


def pipeline_source_credit(source: dict) -> dict:
    record = {
        "attribution": source["creator"],
        "observer": source["observer"],
        "source_url": source["source_url"],
        "photo_license": source["licence"],
        "observation_license": source["observation_licence"],
    }
    refuse_unadmitted(record["photo_license"], record["observation_license"])
    return {**source, "rights": terms(record)}


def validate_pipeline_evidence(pipeline: Path, proof: dict) -> None:
    try:
        saved = json.loads((pipeline / "model-evidence.json").read_text())
        photo = saved["photo"]
        selected = {
            "run_id": saved["run_id"],
            "photo_id": photo["id"],
            "source_photo_id": photo["photo_id"],
        }
        if (
            selected != proof["selection"]
            or selected["run_id"] != "segmentation-experiment-v1"
            or selected["source_photo_id"] != 447484684
        ):
            raise ValueError("Different selected source")
        expected = {
            "creator": photo["attribution"],
            "observer": photo["observer"],
            "licence": photo["photo_license"],
            "observation_licence": photo["observation_license"],
            "source_url": photo["source_url"],
            "source_image_sha256": photo["sha256"],
        }
        if any(proof["source"].get(key) != value for key, value in expected.items()):
            raise ValueError("Different source credit or image")
        if (
            saved["model"] != proof["baseline"]
            or photo["scores"]["segmentation"]["provenance"] != proof["segmentation"]
        ):
            raise ValueError("Different model evidence")
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise ValueError("Pipeline saved evidence does not match selected source/model") from error


def validate_pipeline_capture(pipeline: Path) -> dict:
    try:
        proof = json.loads((pipeline / "capture-manifest.json").read_text())
    except (OSError, ValueError) as error:
        raise ValueError("Pipeline browser capture verification is missing or malformed") from error
    if (
        not isinstance(proof, dict)
        or proof.get("captureSuccess") is not True
        or proof.get("browser_errors") != []
    ):
        raise ValueError("Pipeline browser capture must finish without browser errors")
    checked_files(pipeline, PIPELINE_MEDIA, proof.get("media_sha256"))
    source = proof.get("source")
    if (
        not isinstance(source, dict)
        or source.get("source_image_sha256") != proof["media_sha256"]["source-reference.png"]
    ):
        raise ValueError("Pipeline source image differs from its capture receipt")
    pipeline_source_credit(source)
    validate_pipeline_evidence(pipeline, proof)
    return proof


def render(args: argparse.Namespace) -> None:
    output = new_output(args.output)
    configure_fonts(getattr(args, "ui_font", None), getattr(args, "ui_bold_font", None))
    validate_credit_font(args.credit_font)
    pipeline = validate_pipeline_capture(args.pipeline)
    sources = json.loads((args.captures / "review-snapshot/capture-provenance.json").read_text())
    bird = photo_record(sources, "images/460347209.png")
    if not isinstance(bird.get("rights"), dict):
        raise ValueError("Fresh snapshot photo and observation rights are required")
    bird_bytes = verified_photo_bytes(args.captures, "images/460347209.png", sources)
    with tempfile.TemporaryDirectory(prefix="weedz-checked-pipeline-") as private:
        checked = Path(private) / "pipeline"
        checked.mkdir()
        checked_files(args.pipeline, PIPELINE_MEDIA, pipeline["media_sha256"], checked)
        (checked / "capture-manifest.json").write_text(json.dumps(pipeline))
        captures = Path(private) / "captures"
        snapshot = captures / "review-snapshot"
        (snapshot / "images").mkdir(parents=True)
        (snapshot / "images/460347209.png").write_bytes(bird_bytes)
        (snapshot / "capture-provenance.json").write_text(json.dumps(sources))
        _render(args, output, pipeline, checked, captures, sources)


def _render(
    args: argparse.Namespace,
    output: Path,
    pipeline: dict,
    checked: Path,
    captures: Path,
    sources: dict,
) -> None:
    scenes = load_timeline(args.script, args.audio)
    measured = json.loads(args.transcript.read_text())
    flattened = [
        {
            "scene": scene["scene"],
            "file": scene["file"],
            "words": [w for segment in scene["segments"] for w in segment["words"]],
        }
        for scene in measured["scenes"]
    ]
    with tempfile.TemporaryDirectory(prefix="weedz-caption-") as private:
        aligned = Path(private) / "words.json"
        aligned.write_text(json.dumps(flattened))
        cues = caption_cues(scenes, aligned)
    output.mkdir(parents=True, exist_ok=False)
    narration_master(scenes, output / "narration-native-24k.wav")
    (output / "weedz-demo.srt").write_text(srt(cues))
    frames = WebsiteFrames(captures, checked, args.ffmpeg, args.credit_font)
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
    credits = {
        "project": "https://github.com/gardner/weedz",
        "photography": [r for r in sources["photos"] if r["file"] == "images/460347209.png"],
        "pipeline_photo": pipeline_source_credit(pipeline["source"]),
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
        "font": {
            "file": args.credit_font.name,
            "sha256": hashlib.sha256(args.credit_font.read_bytes()).hexdigest(),
        },
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
    parser.add_argument("--ui-font", type=Path)
    parser.add_argument("--ui-bold-font", type=Path)
    parser.add_argument("--credit-font", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--script", type=Path, default=Path("docs/demo/narration-v3.json"))
    render(parser.parse_args())


if __name__ == "__main__":
    main()
