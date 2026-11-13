"""Geometry and ranking tests do not download a model or infer ground truth."""

import numpy as np

from weedz.discovery.inference import region_boxes, summarize_scores


def test_regions_include_whole_frame_and_cover_edges() -> None:
    boxes = region_boxes(1000, 600)
    assert boxes[0] == (0, 0, 1000, 600)
    assert (0, 0, 600, 360) in boxes
    assert (400, 240, 1000, 600) in boxes
    assert all(0 <= x1 < x2 <= 1000 and 0 <= y1 < y2 <= 600 for x1, y1, x2, y2 in boxes)


def test_summary_preserves_raw_similarity_and_best_region() -> None:
    boxes = [(0, 0, 100, 100), (0, 0, 60, 60)]
    scores = np.array([[0.2, 0.3, 0.25, 0.4], [0.35, 0.2, 0.1, 0.3]])
    result = summarize_scores(scores, boxes, ["weed A", "weed B", "weed C", "lookalike"], 3)
    assert result["best_species"] == "weed A"
    assert result["similarity"] == 0.35
    assert result["margin"] == 0.05
    assert result["box"] == [0, 0, 60, 60]
    assert "probability" not in result
    assert len(result["species"]) == 3


def test_window_selection_uses_comparison_margin_not_raw_target_similarity() -> None:
    # A more target-like crop can be even more like a native/comparison label.
    scores = np.array([[0.4, 0.2, 0.2, 0.6], [0.35, 0.2, 0.1, 0.3]])
    boxes = [(0, 0, 100, 100), (0, 0, 60, 60)]
    result = summarize_scores(scores, boxes, ["weed A", "weed B", "weed C", "lookalike"], 3)
    assert result["box"] == [0, 0, 60, 60]
    assert result["similarity"] == 0.35
