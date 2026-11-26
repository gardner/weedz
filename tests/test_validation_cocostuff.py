import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import numpy as np
import pytest

from weedz.validation.cocostuff import PresenceItem, PresencePrediction, presence_metrics
from weedz.validation.cocostuff_data import (
    Download,
    Instance,
    Masks,
    instance_mask,
    label_masks,
    parse_labels,
    potted_instances,
    vegetation_stratum,
    verified_download,
)
from weedz.validation.cocostuff_regions import proposal_metrics


def test_indexed_labels_keep_person_and_food_separate_from_void() -> None:
    ids = parse_labels("0: unlabeled\n1: person\n52: banana\n64: potted plant\n169: tree\n")
    masks = label_masks(np.array([[0, 51, 63, 168, 255]], dtype=np.uint8), ids)
    assert masks.vegetation.tolist() == [[False, False, True, True, False]]
    assert masks.void.tolist() == [[False, False, False, False, True]]
    assert masks.stratum == "large"


def test_negative_rule_and_positive_with_void() -> None:
    ids = parse_labels("0: unlabeled\n1: person\n169: tree\n")
    pixels = np.zeros((10, 10), dtype=np.uint8)
    pixels[0, :2] = 255
    assert label_masks(pixels, ids).stratum == "negative"
    pixels[0, 2] = 255
    assert label_masks(pixels, ids).stratum == "unassessable"
    pixels[1, 0] = 168
    assert label_masks(pixels, ids).stratum == "small"


def test_stratum_boundaries() -> None:
    assert [vegetation_stratum(n, 1000) for n in (1, 5, 6, 20, 21, 100, 101)] == [
        "tiny",
        "tiny",
        "small",
        "small",
        "medium",
        "medium",
        "large",
    ]


def test_presence_tunes_on_development_and_scores_held_out() -> None:
    items = [
        PresenceItem("dev-positive", "tiny", "development"),
        PresenceItem("dev-negative", "negative", "development"),
        PresenceItem("test-tiny", "tiny", "held-out"),
        PresenceItem("test-large", "large", "held-out"),
        PresenceItem("test-negative", "negative", "held-out"),
        PresenceItem("test-void", "unassessable", "held-out"),
    ]
    scores = {
        "dev-positive": 0.4,
        "dev-negative": 0.3,
        "test-tiny": 0.2,
        "test-large": 0.4,
        "test-negative": 0.5,
    }

    def predict(item: PresenceItem) -> PresencePrediction:
        value = scores[item.source_id]
        return PresencePrediction(value, value >= 0.5)

    threshold, metrics = presence_metrics(items, predict)
    assert threshold == 0.4
    counts = {(metric.name, metric.stratum): (metric.successes, metric.total) for metric in metrics}
    assert counts["recall", "tiny"] == (0, 1)
    assert counts["recall", "large"] == (1, 1)
    assert counts["false_alarm_rate", "all"] == (1, 1)
    assert counts["baseline_recall", "large"] == (0, 1)
    assert counts["baseline_false_alarm_rate", "all"] == (1, 1)


def test_a_threshold_that_flags_every_photo_is_unreachable() -> None:
    items = [
        PresenceItem("dev-scored", "large", "development"),
        PresenceItem("dev-unscored", "tiny", "development"),
        PresenceItem("test-positive", "tiny", "held-out"),
        PresenceItem("test-negative", "negative", "held-out"),
    ]
    scores = {"dev-scored": 0.4, "dev-unscored": 0.0, "test-positive": 0.0, "test-negative": 0.0}

    def predict(item: PresenceItem) -> PresencePrediction:
        return PresencePrediction(scores[item.source_id], scores[item.source_id] > 0)

    threshold, metrics = presence_metrics(items, predict)
    assert threshold is None
    counts = {(metric.name, metric.stratum): (metric.successes, metric.total) for metric in metrics}
    assert counts["recall", "all"] == (0, 0)  # unmeasured, not zero
    assert counts["baseline_recall", "all"] == (0, 1)


def test_a_photo_counts_as_covered_only_when_half_its_vegetation_is() -> None:
    vegetation = np.zeros((10, 10), dtype=bool)
    vegetation[0, :5] = True
    small = np.zeros_like(vegetation)
    small[0, :2] = True
    metrics = proposal_metrics(Masks(vegetation, np.zeros_like(vegetation)), [small], [])
    counts = {(row.name, row.stratum): (row.successes, row.total) for row in metrics}
    assert counts["half_covered_images", "all"] == (0, 1)
    assert ("pixel_recall", "all") not in counts


def test_proposals_score_union_instances_and_labelled_background() -> None:
    vegetation = np.zeros((10, 10), dtype=bool)
    vegetation[0, :4] = True
    void = np.zeros_like(vegetation)
    void[1] = True
    left = np.zeros_like(vegetation)
    left[0, :2] = True
    right = np.zeros_like(vegetation)
    right[0, 2:4] = True
    background = np.zeros_like(vegetation)
    background[2] = True
    with_unknown = np.zeros_like(vegetation)
    with_unknown[1] = True
    with_unknown[2, :2] = True
    at_background_threshold = np.zeros_like(vegetation)
    at_background_threshold[1, :2] = True
    at_background_threshold[2, :8] = True
    metrics = proposal_metrics(
        Masks(vegetation, void),
        [left, right, background, with_unknown, at_background_threshold],
        [left],
    )
    counts = {(row.name, row.stratum): (row.successes, row.total) for row in metrics}
    assert counts["half_covered_images", "medium"] == (1, 1)
    assert counts["component_iou_recall", "medium"] == (1, 1)
    assert counts["component_coverage_recall", "medium"] == (1, 1)
    assert counts["potted_plant_iou_recall", "small"] == (1, 1)
    assert counts["nonvegetation_proposal_share", "all"] == (2, 5)


def test_single_proposal_coverage_and_budget() -> None:
    vegetation = np.zeros((10, 10), dtype=bool)
    vegetation[0, :5] = True
    left = vegetation.copy()
    left[0, 2:] = False
    right = vegetation.copy()
    right[0, :2] = False
    right[0, 4:] = False
    metrics = proposal_metrics(
        Masks(vegetation, np.zeros_like(vegetation)),
        [left, *([right] * 99), vegetation],
        [],
    )
    counts = {(row.name, row.stratum): (row.successes, row.total) for row in metrics}
    assert counts["half_covered_images", "all"] == (1, 1)
    assert counts["component_iou_recall", "all"] == (0, 1)
    assert counts["component_coverage_recall", "all"] == (0, 1)
    assert counts["nonvegetation_proposal_share", "all"] == (0, 100)


def test_instance_selection_and_polygon_coordinates() -> None:
    plant: Instance = {
        "image_id": 12,
        "category_id": 64,
        "iscrowd": 0,
        "segmentation": [[1, 0, 3, 0, 3, 2, 1, 2]],
    }
    instances = potted_instances([plant, {**plant, "iscrowd": 1}, {**plant, "category_id": 1}], 64)
    assert instances == {"12": [plant]}
    assert instance_mask(plant, (2, 4)).tolist() == [[False, True, True, False]] * 2


def test_download_reuses_verified_partial_and_rejects_corrupt_archive(tmp_path: Path) -> None:
    encoded = b"public data fixture"
    pin = Download("https://example.test/data.zip", hashlib.sha256(encoded).hexdigest())
    archive = tmp_path / "data.zip"
    partial = archive.with_suffix(".zip.part")
    partial.write_bytes(encoded)
    assert verified_download(pin, archive).read_bytes() == encoded
    assert not partial.exists()
    archive.write_bytes(b"damaged")
    with pytest.raises(ValueError, match="Checksum mismatch"):
        verified_download(pin, archive)


def test_download_resumes_at_existing_byte_offset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "data.zip"
    archive.with_suffix(".zip.part").write_bytes(b"abc")
    pin = Download("https://example.test/data.zip", hashlib.sha256(b"abcdef").hexdigest())

    @contextmanager
    def stream(
        method: str, url: str, *, headers: dict[str, str], follow_redirects: bool, timeout: int
    ) -> Iterator[httpx.Response]:
        assert headers["Range"] == "bytes=3-"
        yield httpx.Response(
            206,
            headers={"Content-Range": "bytes 3-5/6"},
            request=httpx.Request(method, url),
            stream=httpx.ByteStream(b"def"),
        )

    monkeypatch.setattr(httpx, "stream", stream)
    assert verified_download(pin, archive).read_bytes() == b"abcdef"


def test_sam_proposals_refuse_photos_with_an_exif_rotation(tmp_path: Path):
    # SAM3 masks are in the EXIF-upright frame; COCO-Stuff pixel maps are in the stored frame.
    from PIL import Image

    from weedz.validation.cocostuff_models import sam_predictor
    from weedz.validation.registry import RunContext

    photo = tmp_path / "000000000001.jpg"
    exif = Image.Exif()
    exif[0x0112] = 3
    Image.new("RGB", (40, 40)).save(photo, exif=exif)
    predict = sam_predictor(RunContext(tmp_path, tmp_path, device="cuda:0"))
    with pytest.raises(ValueError, match="EXIF orientation 3"):
        predict(photo)


def test_cached_evidence_is_keyed_by_the_dataset_adapters():
    from weedz.validation import cocostuff_models, inat2021_models, openimages

    for sources in (
        *inat2021_models.PIPELINE_SOURCES.values(),
        *openimages.PIPELINE_SOURCES.values(),
    ):
        assert any(path.parts[0] == "validation" for path in sources), sources
    assert Path("validation/cocostuff_models.py") in cocostuff_models.ADAPTER_SOURCES
