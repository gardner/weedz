"""Value-first film frames from actual segmentation and review evidence."""

import json
import math
import sys
from pathlib import Path

from demo_decoder import CaptureDecoder
from demo_frames import ACCENT, CREAM, MUTED, Frames, text
from PIL import Image, ImageDraw, ImageFont


class WebsiteFrames(Frames):
    def __init__(self, captures: Path, pipeline: Path, ffmpeg: Path, credit_font: Path) -> None:
        super().__init__(captures, ffmpeg, 24, credit_font, pipeline)
        self.pipeline = pipeline
        self.pipeline_decoder: CaptureDecoder | None = None
        self.last_pipeline: Image.Image | None = None

    def evidence_photo(
        self, canvas: Image.Image, filename: str, box: tuple[int, int, int, int]
    ) -> None:
        key = str(self.pipeline / filename)
        if key not in self.images:
            with Image.open(key) as source:
                self.images[key] = source.convert("RGB")
        self.photo(canvas, key, box)

    def intro(self, elapsed: float) -> Image.Image:
        canvas = self.base("SMALL CLUES. HEALTHIER LANDSCAPES.")
        text(canvas, (80, 180), "Help protect the\nplaces you love.", 72, bold=True, width=22)
        text(canvas, (85, 445), "Start with photographs\nthat already exist.", 39, MUTED, width=30)
        self.photo(canvas, "review-snapshot/images/460347209.png", (840, 120, 1000, 730))
        text(canvas, (85, 735), "Find evidence worth a second look.", 31, ACCENT, width=38)
        return canvas

    def pipeline_flow(self, elapsed: float) -> Image.Image:
        canvas = self.base("FROM A PHOTOGRAPH TO A USEFUL LEAD")
        text(canvas, (80, 135), "Keep the evidence connected.", 60, bold=True, width=55)
        draw = ImageDraw.Draw(canvas)
        labels = [
            ("PHOTOGRAPH", "Original scene"),
            ("REGIONS", "SAM2.1 masks"),
            ("COMPARISONS", "BioCLIP + lookalikes"),
            ("REVIEW", "Human assessment"),
        ]
        active = min(3, int(elapsed / 4))
        for i, (label, detail) in enumerate(labels):
            x = 80 + i * 465
            draw.rounded_rectangle(
                (x, 350, x + 410, 620),
                radius=20,
                fill="#244f3e",
                outline=ACCENT if i == active else "#426c56",
                width=3,
            )
            text(canvas, (x + 24, 400), label, 28, ACCENT, True, width=22)
            text(canvas, (x + 24, 490), detail, 27, MUTED, width=21)
            if i < 3:
                draw.line((x + 422, 485, x + 450, 485), fill=ACCENT, width=4)
                draw.polygon(((x + 450, 485), (x + 440, 477), (x + 440, 493)), fill=ACCENT)
        text(
            canvas, (85, 740), "Original photo + source + model evidence", 36, CREAM, True, width=70
        )
        text(
            canvas,
            (85, 815),
            "Region proposals add evidence; original screening order is retained.",
            27,
            MUTED,
            width=100,
        )
        return canvas

    def segmentation(self, elapsed: float) -> Image.Image:
        canvas = self.base("REAL SAM2.1 REGION PROPOSALS")
        text(canvas, (80, 105), "See the shapes. Keep the original.", 52, bold=True, width=65)
        filename = (
            "original-ui.png"
            if elapsed < 5
            else "mask-1-ui.png"
            if elapsed < 13
            else "mask-2-ui.png"
        )
        self.evidence_photo(canvas, filename, (80, 220, 1280, 620))
        text(canvas, (1410, 300), "SAM2.1\nHiera tiny", 37, ACCENT, True, width=18)
        text(canvas, (1410, 460), "Two actual\nflower masks", 30, CREAM, width=20)
        text(canvas, (1410, 620), "Recorded output\nfrom real inference", 25, MUTED, width=22)
        text(
            canvas,
            (85, 865),
            "A proposed shape is not a species identification.",
            29,
            MUTED,
            width=100,
        )
        return canvas

    def comparisons(self, elapsed: float) -> Image.Image:
        canvas = self.base("COMPARE WEEDS AND LOOKALIKES")
        filename = "classification-1-ui.png" if elapsed < 14 else "classification-2-ui.png"
        self.evidence_photo(canvas, filename, (80, 110, 1760, 700))
        text(
            canvas,
            (85, 845),
            "Original screening scores order the queue. Region scores stay separate.",
            29,
            ACCENT,
            width=100,
        )
        return canvas

    def review(self, elapsed: float) -> Image.Image:
        canvas = self.base("THE EVIDENCE, READY TO REVIEW")
        if elapsed < 15.6:
            if self.pipeline_decoder is None:
                self.pipeline_decoder = CaptureDecoder(
                    [
                        str(self.ffmpeg),
                        "-v",
                        "error",
                        "-i",
                        str(self.pipeline / "sam21-pipeline-ui.mp4"),
                        "-vf",
                        "fps=24:eof_action=pass,scale=1536:864",
                        "-frames:v",
                        str(math.ceil(15.6 * 24)),
                        "-f",
                        "rawvideo",
                        "-pix_fmt",
                        "rgb24",
                        "-",
                    ],
                    (1536, 864),
                    math.ceil(15.6 * 24),
                    "Website pipeline",
                )
            self.last_pipeline = self.pipeline_decoder.frame()
            canvas.paste(self.last_pipeline, (192, 80))
        else:
            self.evidence_photo(canvas, "human-review-controls.png", (150, 120, 1620, 740))
        return canvas

    def outcome(self, elapsed: float) -> Image.Image:
        canvas = self.base("MAKE THE NEXT LOOK COUNT")
        text(canvas, (80, 145), "A lead someone can check.", 64, bold=True, width=50)
        self.evidence_photo(canvas, "original-ui.png", (80, 285, 1100, 530))
        for index, label in enumerate(
            ("Inspect the original", "Check the source", "Compare lookalikes", "Record uncertainty")
        ):
            text(canvas, (1240, 330 + index * 115), label, 31, ACCENT, width=25)
        return canvas

    def evidence(self, elapsed: float) -> Image.Image:
        canvas = self.base("OPEN SOURCE. TESTABLE EVIDENCE.")
        text(canvas, (80, 145), "Measure the conservation value.", 60, bold=True, width=55)
        for index, (label, detail) in enumerate(
            [
                ("USEFUL FINDINGS", "Checked by people"),
                ("REVIEW EFFORT", "Time spent per useful lead"),
                ("BETTER EVIDENCE", "Measure segmentation against the baseline"),
            ]
        ):
            y = 330 + index * 175
            text(canvas, (90, y), label, 34, ACCENT, True, width=40)
            text(canvas, (95, y + 65), detail, 30, MUTED, width=85)
        return canvas

    def closing(self, elapsed: float) -> Image.Image:
        canvas = self.base("OPEN-SOURCE TOOLS FOR CONSERVATION")
        text(canvas, (80, 130), "Turn a photograph into a useful lead.", 60, bold=True, width=55)
        text(canvas, (85, 275), "github.com/gardner/weedz", 39, ACCENT, width=70)
        text(
            canvas,
            (85, 380),
            "Next: easier contributions from a mobile camera roll.",
            31,
            MUTED,
            width=85,
        )
        source = json.loads((self.pipeline / "capture-manifest.json").read_text())["source"]
        records = json.loads(
            (self.captures / "review-snapshot/capture-provenance.json").read_text()
        )["photos"]
        records = [r for r in records if r["file"] == "images/460347209.png"]
        creators = [source["creator"]] + [r["creator_attribution"] for r in records]
        draw = ImageDraw.Draw(canvas)
        credit_font = ImageFont.truetype(str(self.credit_font), 25)
        draw.multiline_text(
            (85, 515), "\n".join(creators), font=credit_font, fill=CREAM, spacing=13
        )
        text(
            canvas,
            (85, 660),
            "Non-commercial demo: photo and observation-data terms are separate. "
            "Full source links accompany this film.",
            25,
            MUTED,
            width=100,
        )
        text(
            canvas,
            (85, 755),
            "AI narration: Breeze TTS 2 · Original AI instrumental: MiniMax Music3",
            25,
            MUTED,
            width=105,
        )
        return canvas

    def render(self, scene: int, elapsed: float) -> Image.Image:
        methods = (
            self.intro,
            self.pipeline_flow,
            self.segmentation,
            self.comparisons,
            self.review,
            self.outcome,
            self.evidence,
            self.closing,
        )
        return methods[scene](elapsed)

    def close(self) -> None:
        try:
            if self.pipeline_decoder is not None:
                self.pipeline_decoder.close(check=sys.exc_info()[0] is None)
        finally:
            super().close()
