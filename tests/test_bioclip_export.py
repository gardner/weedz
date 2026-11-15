"""Editable BioCLIP labels remain tentative margin suggestions, not probabilities."""

import json

from test_bioclip_batches import score
from test_bioclip_workflow import model
from test_classification_regions import inputs

from weedz.annotation.bioclip import frame_prediction, regional_prediction


def test_frame_keeps_negative_scores_and_unknown():
    result = frame_prediction(score(), model().profile_metadata("frame"))
    assert result["result"][0]["value"]["text"] == ["Unknown"]
    assert "BioCLIP" in result["model_version"]
    evidence = json.loads(result["result"][1]["value"]["text"][0])
    assert evidence["scores"]["species"][0]["margin"] == -0.2
    assert "softmax" not in json.dumps(result)


def test_regions_use_real_masks_all_three_views_and_unknown(tmp_path):
    _, _, proposal = inputs(tmp_path)
    region = proposal["segmentation"]["regions"][0]
    from test_batch_sam3 import metadata as sam3_metadata

    proposer = {
        **sam3_metadata(),
        "profile": "sam3-image-concept-v1",
        "config": proposal["segmentation"]["provenance"]["config"],
    }
    result = regional_prediction(
        [region],
        [{"id": region["id"], "views": {name: score() for name in ("tight", "masked", "context")}}],
        model().profile_metadata("regions", proposer),
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


def test_margin_builders_refuse_unregistered_or_mislabeled_model_identity():
    import pytest

    with pytest.raises(ValueError, match="identity"):
        frame_prediction(score(), {"classifier_kind": "bioclip-margin-cuda-v1", "scope": "frame"})
