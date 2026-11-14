"""Documentary frames composed from source-credited photos and actual product captures."""

import json
import math
import subprocess
import textwrap
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

SIZE = (1920, 1080)
BG = "#153c2f"
CREAM = "#f4f5e9"
MUTED = "#b7cfc1"
ACCENT = "#c5e79a"


@lru_cache(maxsize=24)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    suffix = "-Bold" if bold else ""
    return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/DejaVuSans{suffix}.ttf", size)


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
    def __init__(self, captures: Path, ffmpeg: Path, fps: int, credit_font: Path) -> None:
        self.captures = captures
        self.ffmpeg = ffmpeg
        self.fps = fps
        self.credit_font = credit_font
        self.decoder: subprocess.Popen[bytes] | None = None
        self.last_web: Image.Image | None = None
        self.images: dict[str, Image.Image] = {}

    def image(self, relative: str) -> Image.Image:
        if relative not in self.images:
            with Image.open(self.captures / relative) as original:
                self.images[relative] = original.convert("RGB")
        return self.images[relative]

    def base(self, label: str) -> Image.Image:
        canvas = Image.new("RGB", SIZE, BG)
        text(canvas, (80, 35), "WEEDZ  /  " + label, 24, ACCENT, True, 110)
        return canvas

    def photo(
        self, canvas: Image.Image, relative: str, box: tuple[int, int, int, int], zoom: float = 1.0
    ) -> None:
        x, y, width, height = box
        image = self.image(relative)
        if zoom > 1:
            half_w, half_h = image.width / zoom / 2, image.height / zoom / 2
            cx, cy = image.width / 2, image.height / 2
            image = image.crop((cx - half_w, cy - half_h, cx + half_w, cy + half_h))
        image = ImageOps.contain(image, (width, height), Image.Resampling.LANCZOS)
        canvas.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))

    def intro(self, elapsed: float) -> Image.Image:
        canvas = self.base("A SECOND LOOK")
        self.photo(
            canvas,
            "review-snapshot/images/460347209.png",
            (760, 130, 1080, 720),
            1 + elapsed * 0.004,
        )
        text(canvas, (80, 240), "What else did\nthis photo\ncapture?", 76, bold=True, width=18)
        text(canvas, (85, 600), "Ordinary photographs.\nOverlooked possibilities.", 32, MUTED)
        text(
            canvas,
            (80, 904),
            "Public skink observation · iNaturalist 256716592 · CC0",
            22,
            MUTED,
            width=120,
        )
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
        text(
            canvas,
            (80, 912),
            "Schematic search windows · a ranking for human investigation",
            23,
            MUTED,
            width=110,
        )
        return canvas

    def web_frame(self, elapsed: float) -> Image.Image:
        canvas = self.base("ACTUAL REVIEW DESK  /  LICENSED DEMO COPY")
        if elapsed < 13.0:
            if self.decoder is None:
                self.decoder = subprocess.Popen(
                    [
                        str(self.ffmpeg),
                        "-v",
                        "error",
                        "-i",
                        str(self.captures / "web-final/web-review-interactions.webm"),
                        "-vf",
                        f"fps={self.fps},scale=1536:864",
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "rgb24",
                        "-",
                    ],
                    stdout=subprocess.PIPE,
                )
            assert self.decoder.stdout is not None
            data = self.decoder.stdout.read(1536 * 864 * 3)
            if len(data) == 1536 * 864 * 3:
                self.last_web = Image.frombytes("RGB", (1536, 864), data)
            if self.last_web is not None:
                canvas.paste(self.last_web, (192, 82))
        else:
            name = "web-reference-comparison.png" if elapsed < 18 else "web-candidate-window.png"
            self.photo(canvas, "web-final/" + name, (192, 82, 1536, 864))
        text(
            canvas,
            (80, 918),
            "Original pilot scores · coordinates withheld · no live writes",
            20,
            MUTED,
            width=120,
        )
        return canvas

    def phone(self, elapsed: float, approval: bool) -> Image.Image:
        if approval:
            states = ("photo", "choices", "approved")
            filename = "flutter-approval-" + states[min(int(elapsed / 9), 2)] + ".png"
            title = "Your library.\nYour decision."
            details = "Library access\n\nIndividual report approval\n\nSeparate choices"
        else:
            filename = "flutter-approval-choices.png"
            title = "See what\nwould be sent."
            details = "Photo attachment\n\nPhoto licence\n\nLocation choice"
        canvas = self.base("ACTUAL FLUTTER WIDGETS  /  PHONE PROTOTYPE")
        text(canvas, (100, 190), title, 74, bold=True, width=22)
        text(canvas, (110, 460), details, 32, MUTED)
        self.photo(canvas, "flutter/" + filename, (1230, 92, 420, 840))
        text(
            canvas,
            (100, 880),
            "Native inference: performance and parity work remains",
            24,
            ACCENT,
            width=72,
        )
        text(
            canvas,
            (100, 920),
            "Synthetic report · public gorse photo · no upload",
            22,
            MUTED,
            width=100,
        )
        return canvas

    def flow(self, elapsed: float) -> Image.Image:
        canvas = self.base("APPROVED REPORTS  /  SEPARATE SERVER INTAKE")
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
        text(
            canvas,
            (100, 925),
            "Intended end-to-end workflow · integration work continues",
            22,
            MUTED,
            width=115,
        )
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
            "Public photography · iNaturalist · CC BY 4.0 / CC0",
            29,
            MUTED,
            width=100,
        )
        records = json.loads(
            (self.captures / "review-snapshot/capture-provenance.json").read_text()
        )
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
            "Actual review desk + Flutter prototype controls\n"
            "Source links, full creator names and licences: companion credits",
            27,
            MUTED,
            width=100,
        )
        text(
            canvas,
            (90, 865),
            "Research demonstration · uncertainty stays visible",
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
            lambda t: self.phone(t, True),
            lambda t: self.phone(t, False),
            self.flow,
            self.pilot,
            self.credits,
        )
        return methods[scene](elapsed)

    def close(self) -> None:
        if self.decoder is not None:
            if self.decoder.stdout is not None:
                self.decoder.stdout.close()
            if self.decoder.poll() is None:
                self.decoder.terminate()
            self.decoder.wait(timeout=10)


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
