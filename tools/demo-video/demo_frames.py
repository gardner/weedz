"""Documentary frames composed from source-credited photos and actual product captures."""

import json
import math
import sys
import textwrap
from functools import lru_cache
from pathlib import Path

from demo_decoder import CaptureDecoder
from demo_evidence import verified_photo
from PIL import Image, ImageDraw, ImageFont, ImageOps

SIZE = (1920, 1080)
BG = "#153c2f"
CREAM = "#f4f5e9"
MUTED = "#b7cfc1"
ACCENT = "#c5e79a"


_FONT_PATHS = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
)


def configure_fonts(regular: Path | None = None, bold: Path | None = None) -> None:
    global _FONT_PATHS
    paths = (regular or _FONT_PATHS[0], bold or _FONT_PATHS[1])
    try:
        for path in paths:
            ImageFont.truetype(str(path.resolve()), 24)
    except OSError as error:
        raise ValueError("Cannot load UI fonts; supply --ui-font and --ui-bold-font") from error
    _FONT_PATHS = tuple(path.resolve() for path in paths)
    font.cache_clear()


@lru_cache(maxsize=24)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_FONT_PATHS[int(bold)]), size)


def text(
    image: Image.Image,
    xy: tuple[int, int],
    value: str,
    size: int = 32,
    color: str = CREAM,
    bold: bool = False,
    width: int = 44,
) -> None:
    lines = "\n".join("\n".join(textwrap.wrap(line, width=width)) for line in value.split("\n"))
    ImageDraw.Draw(image).multiline_text(xy, lines, font=font(size, bold), fill=color, spacing=12)


class Frames:
    def __init__(
        self,
        captures: Path,
        ffmpeg: Path,
        fps: int,
        credit_font: Path,
        mobile_captures: Path,
        web_captures: Path | None = None,
    ) -> None:
        self.captures = captures
        self.web_captures = web_captures or captures / "web-final"
        self.provenance = json.loads(
            (captures / "review-snapshot/capture-provenance.json").read_text()
        )
        self.ffmpeg = ffmpeg
        self.fps = fps
        self.credit_font = credit_font
        self.mobile_captures = mobile_captures
        self.decoder: CaptureDecoder | None = None
        self.last_web: Image.Image | None = None
        self.mobile_decoder: CaptureDecoder | None = None
        self.last_mobile: Image.Image | None = None
        self.images: dict[str, Image.Image] = {}

    def image(self, relative: str) -> Image.Image:
        if relative not in self.images:
            if relative.startswith("review-snapshot/images/"):
                self.images[relative] = verified_photo(
                    self.captures, relative.removeprefix("review-snapshot/"), self.provenance
                )
            else:
                path = (
                    self.web_captures / relative.removeprefix("web-final/")
                    if relative.startswith("web-final/")
                    else self.captures / relative
                )
                with Image.open(path) as original:
                    self.images[relative] = original.convert("RGB")
        return self.images[relative]

    def base(self, label: str) -> Image.Image:
        canvas = Image.new("RGB", SIZE, BG)
        text(canvas, (80, 35), "WEEDZ  /  " + label, 24, ACCENT, True, 110)
        return canvas

    def photo(self, canvas: Image.Image, relative: str, box: tuple[int, int, int, int]) -> None:
        x, y, width, height = box
        image = self.image(relative)
        image = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
        canvas.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))

    def intro(self, elapsed: float) -> Image.Image:
        canvas = self.base("A SECOND LOOK")
        self.photo(canvas, "review-snapshot/images/460347209.png", (760, 130, 1080, 720))
        text(canvas, (80, 240), "What else did\nthis photo\ncapture?", 76, bold=True, width=18)
        text(canvas, (85, 600), "Ordinary photographs.\nOverlooked possibilities.", 32, MUTED)
        return canvas

    def screening(self, elapsed: float) -> Image.Image:
        canvas = self.base("FROM A PHOTO TO A SHORTLIST")
        text(canvas, (80, 130), "Search the whole scene.", 64, bold=True)
        self.photo(canvas, "review-snapshot/images/460347209.png", (80, 300, 1030, 580))
        draw = ImageDraw.Draw(canvas)
        # Deliberately schematic windows, never presented as measured detection boxes.
        for index, rect in enumerate(
            ((130, 330, 650, 630), (390, 510, 910, 810), (570, 350, 1090, 650))
        ):
            if elapsed > index * 2:
                draw.rectangle(rect, outline=ACCENT, width=4)
        draw.line((1140, 580, 1230, 580), fill=ACCENT, width=4)
        draw.polygon(((1230, 580), (1215, 570), (1215, 590)), fill=ACCENT)
        for index, name in enumerate(("Old man's beard", "Pampas", "Gorse", "+ lookalikes")):
            y = 335 + index * 115
            draw.rounded_rectangle((1290, y, 1820, y + 85), radius=16, fill="#244f3e")
            text(canvas, (1320, y + 20), name, 32, ACCENT if index < 3 else MUTED)
        return canvas

    def web_frame(self, elapsed: float) -> Image.Image:
        canvas = self.base("REVIEW THE EVIDENCE")
        if elapsed < 13.0:
            if self.decoder is None:
                self.decoder = CaptureDecoder(
                    [
                        str(self.ffmpeg),
                        "-v",
                        "error",
                        "-i",
                        str(self.web_captures / "web-review-interactions.webm"),
                        "-t",
                        "13",
                        "-vf",
                        f"fps={self.fps},scale=1536:864",
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "rgb24",
                        "-",
                    ],
                    (1536, 864),
                    13 * self.fps,
                    "Review web",
                )
            self.last_web = self.decoder.frame()
            canvas.paste(self.last_web, (192, 82))
        else:
            name = "web-reference-comparison.png" if elapsed < 18 else "web-candidate-window.png"
            self.photo(canvas, "web-final/" + name, (192, 82, 1536, 864))
        return canvas

    def report_summary(self, elapsed: float) -> Image.Image:
        canvas = self.base("SHARE A SIGHTING")
        text(canvas, (90, 145), "Report the sighting.\nKeep the photo.", 72, bold=True, width=32)
        draw = ImageDraw.Draw(canvas)
        for index, label in enumerate(("Suggested plant", "Recorded location", "Model score")):
            y = 400 + index * 145
            draw.rounded_rectangle((100, y, 1200, y + 106), radius=18, fill="#244f3e")
            text(canvas, (135, y + 27), label, 35, ACCENT)
        self.photo(canvas, "review-snapshot/images/447484684.png", (1370, 180, 400, 650))
        text(canvas, (1365, 860), "Photo stays local", 27, MUTED, width=25)
        return canvas

    def settings(self, elapsed: float) -> Image.Image:
        canvas = self.base("CONTROL AFTER SHARING")
        text(canvas, (90, 180), "Your data.\nYour choice.", 78, bold=True, width=22)
        text(
            canvas,
            (100, 490),
            "Delete shared reports\n\nRevoke access\n\nKeep your original photos",
            32,
            MUTED,
        )
        if elapsed < 10:
            if self.mobile_decoder is None:
                self.mobile_decoder = CaptureDecoder(
                    [
                        str(self.ffmpeg),
                        "-v",
                        "error",
                        "-i",
                        str(self.mobile_captures / "live-flutter-settings.webm"),
                        "-t",
                        "10",
                        "-vf",
                        f"fps={self.fps},scale=390:846",
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "rgb24",
                        "-",
                    ],
                    (390, 846),
                    10 * self.fps,
                    "Mobile settings",
                )
            self.last_mobile = self.mobile_decoder.frame()
            canvas.paste(self.last_mobile, (1240, 90))
        else:
            with Image.open(self.mobile_captures / "live-settings-deleted.png") as original:
                screenshot = ImageOps.contain(
                    original.convert("RGB"), (390, 846), Image.Resampling.LANCZOS
                )
            canvas.paste(screenshot, (1240, 90))
        return canvas

    def flow(self, elapsed: float) -> Image.Image:
        canvas = self.base("FROM APPROVAL TO REVIEW")
        text(canvas, (80, 130), "A contribution needs a clear history.", 58, bold=True, width=55)
        draw = ImageDraw.Draw(canvas)
        labels = ("PERSON", "INTAKE", "SPECIALIST")
        details = ("Approve one report", "Source · model · consent", "Review the evidence")
        for index, label in enumerate(labels):
            x = 95 + index * 620
            draw.rounded_rectangle((x, 350, x + 490, 620), radius=25, fill="#244f3e")
            text(canvas, (x + 34, 400), label, 36, ACCENT, True)
            text(canvas, (x + 34, 485), details[index], 25, MUTED, width=25)
            if index < 2:
                draw.line((x + 510, 485, x + 595, 485), fill=ACCENT, width=4)
                dot = x + 510 + int((elapsed % 3) / 3 * 85)
                draw.ellipse((dot - 7, 478, dot + 7, 492), fill=CREAM)
        text(canvas, (100, 730), "Withdrawal removes report content.", 40, bold=True)
        text(canvas, (100, 815), "A late retry must not restore it.", 32, MUTED)
        return canvas

    def pilot(self, elapsed: float) -> Image.Image:
        canvas = self.base("WHAT HAS BEEN MEASURED")
        text(canvas, (80, 160), "A small pilot. A testable question.", 60, bold=True, width=55)
        for x, count, label in (
            (100, "30", "pilot photographs"),
            (850, "39", "lookalike examples"),
        ):
            text(canvas, (x, 300), count, 150, ACCENT, True)
            text(canvas, (x + 5, 490), label, 36, MUTED)
        text(canvas, (100, 640), "Source-labelled convenience samples", 38, bold=True)
        text(
            canvas,
            (100, 725),
            "These do not establish a detection rate for a photo library.",
            30,
            MUTED,
            width=80,
        )
        if elapsed > 9:
            text(
                canvas,
                (100, 845),
                "NEXT: useful findings · human checks · manageable review cost",
                28,
                ACCENT,
                width=100,
            )
        return canvas

    def credits(self, elapsed: float) -> Image.Image:
        canvas = self.base("OPEN-SOURCE WORK FOR CONSERVATION")
        text(canvas, (80, 120), "Take a second look.", 78, bold=True)
        text(canvas, (85, 240), "github.com/gardner/weedz", 42, ACCENT)
        text(
            canvas,
            (90, 360),
            "Non-commercial demo · photo and observation terms in companion credits",
            29,
            MUTED,
            width=100,
        )
        records = self.provenance
        names = sorted(
            {
                p["creator_attribution"].removeprefix("(c) ").split(", some rights")[0]
                for p in records["photos"]
                if p["license"] != "cc0"
            }
        )
        credit_font = ImageFont.truetype(str(self.credit_font), 27)
        credit_lines = textwrap.wrap(" · ".join(names), width=95)
        ImageDraw.Draw(canvas).multiline_text(
            (90, 425), "\n".join(credit_lines), font=credit_font, fill=CREAM, spacing=12
        )
        text(
            canvas,
            (90, 610),
            "AI-generated narration: Breeze TTS 2\nAI-generated instrumental: MiniMax Music3",
            28,
            MUTED,
            width=90,
        )
        text(
            canvas,
            (90, 730),
            "Source links, creator names and licences accompany this film.",
            27,
            MUTED,
            width=100,
        )
        text(
            canvas,
            (90, 865),
            "Open-source tools for conservation",
            26,
            ACCENT,
            width=110,
        )
        return canvas

    def render(self, scene: int, elapsed: float) -> Image.Image:
        methods = (
            self.intro,
            self.screening,
            self.web_frame,
            self.report_summary,
            self.settings,
            self.flow,
            self.pilot,
            self.credits,
        )
        return methods[scene](elapsed)

    def close(self) -> None:
        failures = []
        for decoder in (self.decoder, self.mobile_decoder):
            if decoder is not None:
                try:
                    decoder.close(check=sys.exc_info()[0] is None)
                except RuntimeError as error:
                    failures.append(error)
        if failures:
            raise failures[0]


def caption(canvas: Image.Image, value: str) -> None:
    draw = ImageDraw.Draw(canvas)
    lines = textwrap.wrap(value, width=64)
    y = 1040 - len(lines) * 39
    draw.rounded_rectangle((120, y - 12, 1800, 1066), radius=10, fill="#091d15")
    for line in lines:
        length = draw.textlength(line, font=font(31))
        draw.text(((1920 - length) / 2, y), line, font=font(31), fill=CREAM)
        y += 39


def dissolve(current: Image.Image, previous: Image.Image | None, elapsed: float) -> Image.Image:
    if previous is None or elapsed >= 0.4:
        return current
    alpha = (1 - math.cos(min(1.0, elapsed / 0.4) * math.pi)) / 2
    return Image.blend(previous, current, alpha)
