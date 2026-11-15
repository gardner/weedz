"""Editable BioCLIP labels remain tentative margin suggestions, not probabilities."""

import json

from test_bioclip_batches import score
from test_classification_regions import inputs

from weedz.annotation.bioclip import frame_prediction, regional_prediction


def test_frame_keeps_negative_scores_and_unknown():
    result = frame_prediction(
        score(), {"classifier_kind": "bioclip-margin-cuda-v1", "scope": "frame"}
    )
    assert result["result"][0]["value"]["text"] == ["Unknown"]
    assert "BioCLIP" in result["model_version"]
    evidence = json.loads(result["result"][1]["value"]["text"][0])
    assert evidence["scores"]["species"][0]["margin"] == -0.2
    assert "softmax" not in json.dumps(result)


def test_regions_use_real_masks_all_three_views_and_unknown(tmp_path):
    _, _, proposal = inputs(tmp_path)
    region = proposal["segmentation"]["regions"][0]
    result = regional_prediction(
        [region],
        [{"id": region["id"], "views": {name: score() for name in ("tight", "masked", "context")}}],
        {"classifier_kind": "bioclip-margin-cuda-v1", "scope": "regions"},
        (64, 64),
    )
    assert any(
        row["type"] == "brushlabels" and row["value"]["brushlabels"] == ["Unknown"]
        for row in result["result"]
    )
    assert any(
        row["type"] == "textarea" and row["value"]["text"] == ["Unknown"]
        for row in result["result"]
    )
