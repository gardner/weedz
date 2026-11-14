"""The common sample contract keeps unknowns explicit and refuses unsupported tasks."""

from typing import Any

import pytest
from pydantic import ValidationError

from weedz.contract import SCHEMA_VERSION, Sample, UnsupportedTask, require_task

SHA = "a" * 64


def annotation(**fields: Any) -> dict[str, Any]:
    return {
        "id": "a1",
        "supervision": "image_class",
        "taxon": "Ulex europaeus",
        "label": "present",
        "origin": "source",
    } | fields


def sample(**fields: Any) -> dict[str, Any]:
    return {
        "id": "test:1",
        "source": "test",
        "source_id": "1",
        "snapshot": "rev-1",
        "rights": {
            "media_license": "cc-by",
            "metadata_license": "cc0",
            "creator": "Ana",
            "attribution": "(c) Ana, CC BY",
            "license_source": "https://example.org/1",
        },
        "media": {"uri": "https://example.org/1.jpg", "sha256": SHA, "width": 400, "height": 300},
        "tasks": ["image_classification"],
        "annotations": [annotation()],
    } | fields


def test_a_sample_records_its_schema_version_and_explicit_unknowns() -> None:
    record = Sample.model_validate(sample())
    assert record.schema_version == SCHEMA_VERSION == 1
    assert (record.view, record.scale) == ("unknown", "unknown")
    assert record.geography is None and record.ground is None and record.captured_on is None
    assert record.annotations[0].review == "unreviewed"


def test_a_non_geographic_photo_supports_image_classification_without_coordinates() -> None:
    record = Sample.model_validate(sample(geography=None))
    assert record.geography is None
    require_task(record, "image_classification")


def test_an_image_label_cannot_become_a_mask() -> None:
    with pytest.raises(ValidationError, match="segmentation needs dense_mask"):
        Sample.model_validate(sample(tasks=["segmentation"]))


def test_a_sparse_mask_cannot_become_dense_background() -> None:
    sparse = annotation(supervision="sparse_mask", mask_uri="masks/1.png")
    assert Sample.model_validate(sample(tasks=["sparse_segmentation"], annotations=[sparse]))
    with pytest.raises(ValidationError, match="segmentation needs dense_mask"):
        Sample.model_validate(sample(tasks=["segmentation"], annotations=[sparse]))


def test_area_measurement_needs_known_ground_geometry() -> None:
    dense = annotation(supervision="dense_mask", mask_uri="masks/1.png")
    with pytest.raises(ValidationError, match="ground geometry"):
        Sample.model_validate(sample(tasks=["area_measurement"], annotations=[dense]))
    measured = sample(tasks=["area_measurement"], annotations=[dense], ground={"gsd_m": 0.013})
    assert Sample.model_validate(measured).ground is not None


def test_predictions_rejected_and_unknown_labels_are_not_supervision() -> None:
    prediction = annotation(origin="model", model="bioclip-2", score=0.3)
    rejected = annotation(review="rejected")
    unknown = annotation(label="unknown")
    ignored = annotation(label="ignored")
    for evidence in (prediction, rejected, unknown, ignored):
        with pytest.raises(ValidationError, match="image_classification needs image_class"):
            Sample.model_validate(sample(annotations=[evidence]))


def test_inference_needs_no_supervision() -> None:
    assert Sample.model_validate(sample(tasks=["inference"], annotations=[]))


def test_a_model_prediction_names_its_model() -> None:
    with pytest.raises(ValidationError, match="model"):
        Sample.model_validate(sample(tasks=["inference"], annotations=[annotation(origin="model")]))


def test_occurrence_supervision_needs_a_real_location() -> None:
    occurrence = annotation(supervision="occurrence")
    with pytest.raises(ValidationError, match="location"):
        Sample.model_validate(sample(tasks=["site_selection"], annotations=[occurrence]))
    located = sample(
        tasks=["site_selection"],
        annotations=[occurrence],
        geography={"latitude": -41.3, "longitude": 173.2, "uncertainty_m": 10},
    )
    assert Sample.model_validate(located).geography is not None


@pytest.mark.parametrize(
    "fields,message",
    [
        ({"supervision": "box"}, "box"),
        ({"supervision": "box", "box": [10, 10, 5, 20]}, "box"),
        ({"supervision": "box", "box": [10, 10, 500, 20]}, "inside the image"),
        ({"box": [1, 1, 2, 2]}, "image_class"),
        ({"supervision": "dense_mask"}, "mask_uri"),
        ({"supervision": "dense_mask", "mask_uri": "  "}, "mask_uri"),
        ({"supervision": "surveyed_point", "point": [401, 10]}, "inside the image"),
        ({"supervision": "surveyed_point"}, "point"),
        ({"supervision": "unlabelled"}, "unlabelled"),
    ],
)
def test_geometry_must_fit_its_supervision(fields: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Sample.model_validate(sample(tasks=["inference"], annotations=[annotation(**fields)]))


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_non_finite_numbers_are_refused_because_json_cannot_hold_them(value: float) -> None:
    prediction = annotation(origin="model", model="bioclip-2", score=value)
    for invalid in (
        sample(tasks=["inference"], annotations=[prediction]),
        sample(ground={"gsd_m": value}),
        sample(geography={"latitude": -41.3, "longitude": 173.2, "uncertainty_m": value}),
    ):
        with pytest.raises(ValidationError, match="finite"):
            Sample.model_validate(invalid)


def test_a_sample_rejects_unknown_schema_versions_and_unnamespaced_ids() -> None:
    with pytest.raises(ValidationError):
        Sample.model_validate(sample(schema_version=2))
    with pytest.raises(ValidationError, match="source"):
        Sample.model_validate(sample(id="other:1"))


def test_a_source_name_cannot_contain_the_id_separator() -> None:
    assert Sample.model_validate(sample(id="test:b:c", source_id="b:c"))
    with pytest.raises(ValidationError, match="source"):
        Sample.model_validate(sample(id="test:b:c", source="test:b", source_id="c"))


def test_annotation_ids_are_unique_within_a_sample() -> None:
    with pytest.raises(ValidationError, match="unique"):
        Sample.model_validate(sample(annotations=[annotation(), annotation()]))


def test_a_consumer_refuses_samples_that_do_not_declare_its_task() -> None:
    record = Sample.model_validate(sample())
    with pytest.raises(UnsupportedTask, match="test:1 does not support detection"):
        require_task(record, "detection")
