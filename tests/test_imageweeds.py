"""Mirror-local category IDs are not universal taxon identifiers."""

import pytest

from weedz.labelled.imageweeds import source_boxes


def test_category_identity_is_local_and_boxes_are_xyxy():
    image = {"id": 7, "width": 100, "height": 80}
    annotations = [
        {"id": 10, "image_id": 7, "category_id": 2, "bbox": [4, 5, 6, 7], "segmentation": []}
    ]
    categories = [{"id": 2, "name": "weed:amaranthusretroflexus"}]
    result = source_boxes(image, annotations, categories)
    assert result[0].taxon == "Amaranthus retroflexus"
    assert result[0].box == (4, 5, 10, 12)
    assert result[0].origin == "source" and result[0].review == "unreviewed"
    changed = [{"id": 2, "name": "weed:amaranthustuberculatus"}]
    assert source_boxes(image, annotations, changed)[0].taxon == "Amaranthus tuberculatus"


def test_mismatched_category_and_outside_geometry_refused():
    image = {"id": 1, "width": 10, "height": 10}
    row = {"id": 1, "image_id": 1, "category_id": 2, "bbox": [9, 9, 5, 5]}
    with pytest.raises(ValueError, match="category"):
        source_boxes(image, [row], [])
    with pytest.raises(ValueError, match="bounds"):
        source_boxes(image, [row], [{"id": 2, "name": "weed:bassiascoparia"}])
