"""Machine taxon labels are editable proposals, not human annotations or global truth."""

import base64
import io
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

from weedz.annotation.auto_labels import (
    frame_prediction,
    proposals_prediction,
    regional_prediction,
    sam_prediction,
)
from weedz.annotation.label_studio import label_config


def region() -> dict:
    encoded = io.BytesIO()
    Image.fromarray(np.full((2, 3, 4), 255, dtype=np.uint8)).save(encoded, format="PNG")
    return {
        "id": "actual-mask",
        "box": [0, 0, 6, 4],
        "context_box": [0, 0, 6, 4],
        "mask_size": [3, 2],
        "mask_png": base64.b64encode(encoded.getvalue()).decode(),
        "views": {"tight": {"best_species": "Ulex europaeus", "margin": -0.04}},
    }


def test_frame_species_is_editable_but_does_not_invent_a_mask():
    topk = [
        {"taxon": "Quercus robur L.", "score": 0.2, "score_kind": "closed_set_softmax_uncalibrated"}
    ]
    prediction = frame_prediction(topk, {"revision": "pinned"})
    assert prediction["model_version"].startswith("PlantCLEF frame auto-label")
    result = next(r for r in prediction["result"] if r["from_name"] == "predicted_taxon")
    assert result["value"]["text"] == ["Quercus robur L."]
    assert not result.get("readonly", False)
    assert all(r["type"] != "brushlabels" for r in prediction["result"])
    assert "score" not in prediction and "annotations" not in prediction


def test_sam_negative_is_unknown_and_positive_is_tentative_watchlist_taxon():
    negative = sam_prediction([region()], {"revision": "pinned"}, (6, 4))
    brush = next(r for r in negative["result"] if r["type"] == "brushlabels")
    assert brush["value"]["brushlabels"] == ["Unknown"]
    proposed = region()
    proposed["views"]["masked"] = {"best_species": "Cortaderia selloana", "margin": 0.01}
    positive = sam_prediction([proposed], {"revision": "pinned"}, (6, 4))
    brush = next(r for r in positive["result"] if r["type"] == "brushlabels")
    text = next(r for r in positive["result"] if r["from_name"] == "region_taxon")
    assert brush["value"]["brushlabels"] == ["Cortaderia selloana"]
    assert text["id"] == brush["id"] == "actual-mask"
    assert text["value"]["text"] == ["Cortaderia selloana"]
    assert not text.get("readonly", False)


def test_regional_global_taxonomy_keeps_exact_name_and_proposed_class():
    topk = [{"taxon": "Ulex europaeus L.", "score": 0.1}]
    prediction = regional_prediction([(region(), topk)], {"revision": "pinned"}, (6, 4))
    brush = next(r for r in prediction["result"] if r["type"] == "brushlabels")
    text = next(r for r in prediction["result"] if r["from_name"] == "region_taxon")
    assert brush["value"]["brushlabels"] == ["Ulex europaeus"]
    assert text["value"]["text"] == ["Ulex europaeus L."]
    other = regional_prediction(
        [(region(), [{"taxon": "Quercus robur L.", "score": 0.1}])], {"revision": "pinned"}, (6, 4)
    )
    assert next(r for r in other["result"] if r["type"] == "brushlabels")["value"][
        "brushlabels"
    ] == ["Other plant"]


def test_assisted_fields_allow_humans_to_correct_taxa():
    config = ET.fromstring(label_config("assisted"))
    image = config.find("TextArea[@name='predicted_taxon']")
    per_region = config.find("TextArea[@name='region_taxon']")
    assert image is not None and image.attrib["editable"] == "true"
    assert per_region is not None and per_region.attrib["editable"] == "true"
    assert per_region.attrib["perRegion"] == "true"


def test_proposals_without_classifier_stay_unknown_not_invented_species():
    prediction = proposals_prediction([region()], {"checkpoint": "pinned"}, (6, 4))
    assert prediction["model_version"].startswith("SAM2.1 mask proposals")
    assert "BioCLIP" not in prediction["model_version"]
    assert next(r for r in prediction["result"] if r["type"] == "brushlabels")["value"][
        "brushlabels"
    ] == ["Unknown"]
