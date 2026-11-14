"""Render a visual-only preview from actual Flutter captures, outside Git."""

import argparse
import json
import math
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

SIZE = (1920, 1080)
BACKGROUND = "#153c2f"
CREAM = "#f4f5e9"
MUTED = "#b7cfc1"
ACCENT = "#c5e79a"
STATES = [
    (
        "flutter-approval-photo.png",
        "REVIEW",
        "Every report\nstarts with you.",
        "Review the suggestion before deciding what leaves the phone.",
    ),
    (
        "flutter-approval-choices.png",
        "PHOTO CHOICE",
        "Choose what\nyou share.",
        "A cropped photo and its licence are deliberate choices.",
    ),
    (
        "flutter-approval-approved.png",
        "APPROVAL",
        "Approval is\na separate step.",
        "A suggestion is not a confirmed identification.",
    ),
    (
        "flutter-settings-delete.png",
        "SETTINGS",
        "Keep control\nafter sharing.",
        "Settings provide a route to request deletion.",
    ),
    (
        "flutter-settings-confirmation.png",
        "CONFIRM",
        "Confirm the\nconsequences.",
        "The app explains what will be removed and what remains.",
    ),
    (
        "flutter-settings-pending.png",
        "PENDING",
        "A retry is\nnot success.",
        "Pending deletion stays pending until a valid server receipt arrives.",
    ),
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    suffix = "-Bold" if bold else ""
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/DejaVuSans{suffix}.ttf", size)


def slide(capture: Path, number: int) -> Image.Image:
    filename, label, title, body = STATES[number]
    canvas = Image.new("RGB", SIZE, BACKGROUND)
    draw = ImageDraw.Draw(canvas)
    draw.text((112, 80), "WEEDZ", font=font(30, True), fill=ACCENT)
    draw.text((112, 127), "A second look at everyday photos", font=font(23), fill=MUTED)
    draw.rounded_rectangle((112, 234, 510, 280), radius=23, fill="#244f3e")
    draw.text((133, 243), f"{number + 1:02}  /  {label}", font=font(20, True), fill=ACCENT)
    draw.multiline_text((105, 332), title, font=font(72, True), fill=CREAM, spacing=13)
    draw.multiline_text(
        (112, 563), "\n".join(textwrap.wrap(body, width=35)), font=font(34), fill=MUTED, spacing=14
    )
    draw.text((112, 843), "ACTUAL FLUTTER WIDGETS", font=font(20, True), fill=ACCENT)
    draw.text((112, 883), "Prototype report / public photo / no upload", font=font(22), fill=MUTED)
    draw.text(
        (112, 932), "Visual preview — narration and music to follow", font=font(20), fill=MUTED
    )
    # The complete capture stays visible: no cropped controls or recreated UI.
    with Image.open(capture / filename) as original:
        screenshot = ImageOps.contain(original.convert("RGB"), (450, 900), Image.Resampling.LANCZOS)
    draw.rounded_rectangle((1170, 65, 1652, 1001), radius=38, fill="#091d15")
    draw.rounded_rectangle((1182, 77, 1640, 989), radius=28, fill=CREAM)
    canvas.paste(
        screenshot, (1186 + (450 - screenshot.width) // 2, 83 + (900 - screenshot.height) // 2)
    )
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (112, 1024),
        "Public gorse photo: Saryu Mae · CC BY 4.0 · iNaturalist 250240131 · "
        "full credits accompany video",
        font=font(18),
        fill=MUTED,
    )
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ffmpeg", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=24)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output path; an existing preview is never overwritten")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    slides = [slide(args.captures, index) for index in range(len(STATES))]
    slides[0].save(args.output.with_suffix(".png"))
    seconds = 4
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
        str(args.output),
    ]
    with subprocess.Popen(command, stdin=subprocess.PIPE) as encoder:
        assert encoder.stdin is not None
        for index, current in enumerate(slides):
            following = slides[min(index + 1, len(slides) - 1)]
            for frame in range(seconds * args.fps):
                progress = frame / (seconds * args.fps)
                alpha = max(0.0, min(1.0, (progress - 0.88) / 0.12))
                alpha = (1 - math.cos(alpha * math.pi)) / 2
                image = Image.blend(current, following, alpha) if alpha else current.copy()
                draw = ImageDraw.Draw(image)
                for dot in range(len(STATES)):
                    x = 112 + dot * 115
                    draw.rounded_rectangle(
                        (x, 767, x + 98, 773), radius=3, fill=ACCENT if dot <= index else "#37614d"
                    )
                encoder.stdin.write(image.tobytes())
        encoder.stdin.close()
        if encoder.wait() != 0:
            raise SystemExit("Video encoder failed; inspect the partial artifact before retrying")
    args.output.with_suffix(".json").write_text(
        json.dumps(
            {
                "purpose": "Visual-only prototype preview; no network submission",
                "duration_seconds": seconds * len(STATES),
                "fps": args.fps,
                "captures": [name for name, *_ in STATES],
                "attribution": (
                    "See captures/assets/attribution.json for full source and licence records"
                ),
            },
            indent=2,
        )
        + "\n"
    )
    print(args.output)


if __name__ == "__main__":
    main()
