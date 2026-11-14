"""Committed device goldens must continue matching the server's preprocessing contract."""

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from weedz.discovery.inference import featureless, region_boxes, square_view

FIXTURES = Path(__file__).parents[1] / "mobile/test/fixtures/model_conformance"


def test_device_image_goldens_match_the_server_contract() -> None:
    manifest = json.loads((FIXTURES / "expected.json").read_text())
    for case in manifest["cases"]:
        with Image.open(FIXTURES / case["source"]) as original:
            assert original.getexif().get(0x0112, 1) == case["exif_orientation"]
            upright = ImageOps.exif_transpose(original).convert("RGB")
        assert list(upright.size) == case["upright_size"]
        with Image.open(FIXTURES / case["upright"]) as expected:
            assert np.array_equal(np.asarray(upright), np.asarray(expected))
        assert [list(box) for box in region_boxes(*upright.size)] == [
            row["box"] for row in case["windows"]
        ]
        for index, window in enumerate(case["windows"]):
            box = tuple(window["box"])
            crop = upright.crop(box)
            assert featureless(crop) == window["featureless"]
            assert (index == 0 or not featureless(crop)) == window["eligible"]
            actual_std = float(np.asarray(crop.convert("L")).std())
            assert abs(actual_std - float(window["greyscale_population_std"])) < 1e-9
            with Image.open(FIXTURES / window["square"]) as expected:
                assert np.array_equal(np.asarray(square_view(upright, box)), np.asarray(expected))


def test_checkerboards_cover_both_sides_and_exactly_the_strict_threshold() -> None:
    manifest = json.loads((FIXTURES / "expected.json").read_text())
    for case in manifest["cases"][1:]:
        amplitude = int(case["source"].removeprefix("std-").removesuffix(".png"))
        for window in case["windows"][1:]:
            assert float(window["greyscale_population_std"]) == amplitude
            assert window["featureless"] == (amplitude < 8)
