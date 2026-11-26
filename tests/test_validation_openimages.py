from pathlib import Path

import pytest

from weedz.validation.openimages import box_metrics, presence_metrics, recall_threshold
from weedz.validation.openimages_data import (
    Item,
    LabelBox,
    load_items,
    select_items,
    vegetation_scope,
)
from weedz.validation.splits import split_of


def test_hierarchy_includes_descendants_and_excludes_parts(tmp_path: Path) -> None:
    hierarchy = tmp_path / "hierarchy.json"
    hierarchy.write_text(
        '{"LabelName":"root","Subcategory":[{"LabelName":"plant","Part":[{"LabelName":"part"}],'
        '"Subcategory":[{"LabelName":"tree","Subcategory":[{"LabelName":"palm"}]},'
        '{"LabelName":"flower"}]},{"LabelName":"other"}]}'
    )
    assert vegetation_scope(hierarchy, "plant") == {"plant", "tree", "palm", "flower"}


def test_verified_labels_and_box_strata(tmp_path: Path) -> None:
    labels = tmp_path / "labels.csv"
    labels.write_text(
        "ImageID,Source,LabelName,Confidence\n"
        "a,verification,plant,0.0\n"
        "b,verification,tree,0\n"
        "c,verification,plant,0\n"
        "c,crowdsource-verification,tree,1.0\n"
        "d,verification,plant,1\n"
        "e,verification,tree,1\n"
        "f,verification,tree,1\n"
        "g,verification,plant,1\n"
        "h,machine,plant,0\n"
        "i,verification,plant,0\n"
        "j,verification,plant,1\n"
        "k,verification,plant,1\n"
    )
    boxes = tmp_path / "boxes.csv"
    boxes.write_text(
        "ImageID,LabelName,XMin,XMax,YMin,YMax,IsGroupOf,IsDepiction\n"
        "d,tree,0,0.09,0,0.1,0,0\n"
        "d,tree,0,1,0,1,1,0\n"
        "e,tree,0,0.1,0,0.1,0,0\n"
        "f,tree,0,1,0,1,1,0\n"
        "i,tree,0,1,0,1,0,0\n"
        "j,tree,0,1,0,1,0,1\n"
        "k,tree,0,1,0,1,0,0\n"
    )
    items = load_items(labels, boxes, "plant", {"plant", "tree"})
    assert {item.id: (item.present, item.stratum) for item in items} == {
        "a": (False, "verified-absent"),
        "c": (True, "no-box"),
        "d": (True, "small"),
        "e": (True, "medium"),
        "f": (True, "group-of only"),
        "g": (True, "no-box"),
        "j": (True, "no-box"),
        "k": (True, "large"),
    }


def test_frozen_sample_preserves_small_quota() -> None:
    items = [Item(str(i), True, "large" if i < 1000 else "small", ()) for i in range(1300)]
    cohort = select_items(items, "held-out", positive_budget=100, small_minimum=40)
    assert len(cohort) == 100
    assert all(split_of(item.id) == "held-out" for item in cohort)
    assert sum(item.stratum == "small" for item in cohort) >= 40
    assert cohort == select_items(items[::-1], "held-out", positive_budget=100, small_minimum=40)


def test_threshold_and_held_out_metrics() -> None:
    assert recall_threshold([0.1] + [0.3] * 19) == 0.3
    with pytest.raises(ValueError, match="development"):
        recall_threshold([])
    items = [
        Item("p", True, "small", ()),
        Item("n", False, "verified-absent", ()),
    ]
    rates = presence_metrics(items, {"p": 0.3, "n": 0.29}, 0.3, "test")
    by_key = {(result.name, result.stratum): result for result in rates}
    assert by_key["test_recall", "small"].value == 1
    assert by_key["test_recall", "all"].target == 0.95
    assert by_key["test_false_alarm_rate", "all"].value == 0
    assert by_key["test_false_alarm_rate", "all"].ceiling == 0.1


def test_box_scoring_uses_first_100_and_one_to_one_matching() -> None:
    small = LabelBox((0.0, 0.0, 0.05, 0.05), False)
    large = LabelBox((0.5, 0.5, 1.0, 1.0), False)
    group = LabelBox((0.0, 0.0, 1.0, 1.0), True)
    item = Item("p", True, "large", (small, small, large, group))
    proposals = [small.box, *([(0.1, 0.1, 0.2, 0.2)] * 99), large.box]
    by_stratum = {result.stratum: result for result in box_metrics([item], lambda _: proposals)}
    assert (by_stratum["all"].successes, by_stratum["all"].total) == (1, 3)
    assert by_stratum["small"].value == 0.5
    assert by_stratum["large"].value == 0
    assert by_stratum["medium"].value is None


def test_predictions_resume_without_loading_model(tmp_path: Path) -> None:
    from weedz.validation.openimages import _predict_all

    item = Item("p", True, "small", ())
    image = tmp_path / "p.jpg"
    image.with_suffix(".sha256").write_text("image-digest\n")
    instances = []

    def load():
        instances.append("loaded")
        return lambda _: 0.25

    inputs = ([item], {"p": image}, tmp_path / "predictions", load, float, float)
    assert _predict_all(*inputs) == {"p": 0.25}
    assert _predict_all(*inputs) == {"p": 0.25}
    assert instances == ["loaded"]
    image.with_suffix(".sha256").write_text("updated-digest\n")
    assert _predict_all(*inputs) == {"p": 0.25}
    assert instances == ["loaded", "loaded"]


def test_image_cache_verifies_s3_checksum_and_cached_bytes(tmp_path: Path) -> None:
    import hashlib

    import httpx

    from weedz.validation.openimages_data import IMAGE_URL, image_path

    image_id = "0123456789abcdef"
    image_bytes = b"image bytes"
    requests = []

    def server(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        checksum = hashlib.md5(image_bytes, usedforsecurity=False).hexdigest()
        return httpx.Response(
            200, headers={"etag": f'"{checksum}"'}, stream=httpx.ByteStream(image_bytes)
        )

    with httpx.Client(transport=httpx.MockTransport(server)) as client:
        cached = image_path(tmp_path, image_id, client)
        assert cached.read_bytes() == image_bytes
        image_path(tmp_path, image_id, client)
        assert requests == [IMAGE_URL.format(id=image_id)]
        cached.write_bytes(b"corrupted")
        assert image_path(tmp_path, image_id, client).read_bytes() == image_bytes
        assert len(requests) == 2

    unverified = httpx.MockTransport(
        lambda _: httpx.Response(200, stream=httpx.ByteStream(image_bytes))
    )
    with httpx.Client(transport=unverified) as client, pytest.raises(ValueError, match="checksum"):
        image_path(tmp_path, "234567890abcdef1", client)


def test_profile_changes_with_pipeline_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from weedz.validation import openimages
    from weedz.validation.registry import RunContext

    source = tmp_path / "sam3_image.py"
    source.write_text("original")
    monkeypatch.setitem(openimages.PIPELINE_SOURCES, "sam3", (source,))
    context = RunContext(tmp_path, tmp_path, device="cuda:0")
    original = openimages._profile(context, "sam3")
    source.write_text("updated")
    assert openimages._profile(context, "sam3") != original


def test_sam_boxes_refuse_photos_with_an_exif_rotation(tmp_path: Path):
    # SAM3 returns boxes in the EXIF-upright frame; Open Images boxes use the stored frame.
    from PIL import Image

    from weedz.validation.openimages import _sam_prediction

    photo = tmp_path / "rotated.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.new("RGB", (40, 20)).save(photo, exif=exif)

    class Unused:
        def screen(self, path: Path) -> dict:
            raise AssertionError("SAM3 should not run on a rotated photo")

    with pytest.raises(ValueError, match="EXIF orientation 6"):
        _sam_prediction(Unused(), photo)  # type: ignore[arg-type]
