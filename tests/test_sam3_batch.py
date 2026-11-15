"""Canonical SAM3 batches retain prompt-separated failures and resume completed inference."""

import json

import numpy as np
from test_closed_batch import batch as batch

from weedz.segmentation.sam3_batch import propose_sam3_batch
from weedz.segmentation.sam3_image import Sam3Config, Sam3Image


class Processor:
    def __init__(self):
        self.calls = []
        self.failed = False

    def set_image(self, image):
        return {"size": image.size}

    def reset_all_prompts(self, state):
        pass

    def set_text_prompt(self, *, state, prompt):
        self.calls.append(prompt)
        if prompt == "flower" and not self.failed:
            self.failed = True
            raise RuntimeError("One transient prompt failure")
        width, height = state["size"]
        return {
            "masks": np.ones((1, 1, height, width), bool),
            "scores": np.array([0.8]),
            "boxes": np.array([[0, 0, width, height]]),
        }


def test_partial_prompt_is_not_flattened_and_retry_reuses_completed_prompt(batch):
    root, manifest, _, _ = batch
    processor = Processor()
    model = Sam3Image(processor, Sam3Config(), {"checkpoint": "test"}, root / "model-cache")
    output = root / "sam3-output"
    partial = propose_sam3_batch(manifest, manifest.parent, output, model)
    assert partial["counts"] == {"ok": 0, "empty": 0, "partial": 1, "failed": 0}
    completed = propose_sam3_batch(manifest, manifest.parent, output, model)
    assert completed["counts"] == {"ok": 1, "empty": 0, "partial": 0, "failed": 0}
    assert processor.calls == ["plant", "flower", "flower"]
    assert propose_sam3_batch(manifest, manifest.parent, output, model) == completed
    assert processor.calls == ["plant", "flower", "flower"]
    row = json.loads((output / "proposals.jsonl").read_text())
    assert row["sample_id"] == "deepweeds:source.jpg"
    assert "photo_id" not in row and row["segmentation"]["baseline_retained"] is False
