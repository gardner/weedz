"""Mirror-local category IDs are not universal taxon identifiers."""

import pytest

from weedz.labelled.imageweeds import source_boxes


def test_category_identity_is_local_and_boxes_are_xyxy():
    image = {"id": 7, "width": 100, "height": 80}
    annotations = [
        {"id": 10, "image_id": 7, "category_id": 2, "bbox": [4, 5, 6, 7], "segmentation": []}
    ]
    categories = [{"id": 2, "name": "weed: amaranthus retroflexus"}]
    result = source_boxes(image, annotations, categories)
    assert result[0].taxon == "Amaranthus retroflexus"
    assert result[0].box == (4, 5, 10, 12)
    assert result[0].origin == "source" and result[0].review == "unreviewed"
    changed = [{"id": 2, "name": "weed: amaranthus tuberculatus"}]
    assert source_boxes(image, annotations, changed)[0].taxon == "Amaranthus tuberculatus"


def test_mismatched_category_and_outside_geometry_refused():
    image = {"id": 1, "width": 10, "height": 10}
    row = {"id": 1, "image_id": 1, "category_id": 2, "bbox": [9, 9, 5, 5]}
    with pytest.raises(ValueError, match="category"):
        source_boxes(image, [row], [])
    with pytest.raises(ValueError, match="bounds"):
        source_boxes(image, [row], [{"id": 2, "name": "weed:bassiascoparia"}])


def test_invalid_publisher_box_quarantines_whole_image_without_clipping():
    from weedz.labelled.imageweeds import quarantine

    native = {
        "images": [{"id": 1, "file_name": "one.jpg", "width": 10, "height": 10}],
        "categories": [{"id": 0, "name": "weed: bassia scoparia"}],
        "annotations": [{"id": 2, "image_id": 1, "category_id": 0, "bbox": [9, 0, 2, 2]}],
    }
    assert quarantine(native) == {
        "one.jpg": "Source box outside image bounds; entire image withheld, no clipping"
    }
    assert native["annotations"][0]["bbox"] == [9, 0, 2, 2]


def test_publisher_creator_and_separate_image_metadata_rights_are_preserved():
    from weedz.labelled.imageweeds import LICENCE, source_rights

    native = {
        "info": {"metadata": {"license": LICENCE, "creator": [{"name": "Nitin Rai"}]}},
        "licenses": [{"id": 0, "url": LICENCE}, {"id": 1, "url": "all rights reserved"}],
    }
    rights = source_rights(native, {"license": 0})
    assert rights.creator == "Nitin Rai" and "Nitin Rai" in rights.attribution
    assert rights.media_license == rights.metadata_license == "CC-BY-4.0"
    with pytest.raises(ValueError, match="separately"):
        source_rights(native, {"license": 1})
    native["info"]["metadata"]["license"] = "unknown"
    with pytest.raises(ValueError, match="separately"):
        source_rights(native, {"license": 0})
