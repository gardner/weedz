"""Margin-native runners bind canonical identities without synthetic observations."""

import numpy as np
import pytest
from test_classification_batch import corpus
from test_classification_regions import inputs

from weedz.classification.bioclip_batches import classify_margin_batch
from weedz.discovery.inference import COMPARISONS, summarize_scores
from weedz.discovery.records import SPECIES


def score(width=1, height=1):
    from weedz.discovery.inference import region_boxes

    boxes = region_boxes(width, height)
    raw = np.zeros((len(boxes), len(SPECIES) + len(COMPARISONS)), dtype=np.float32)
    raw[:, 0] = -0.2
    out = summarize_scores(raw, boxes, list(SPECIES) + COMPARISONS, len(SPECIES))
    out["window_similarities"] = raw.tolist()
    out["window_boxes"] = [list(box) for box in boxes]
    out.update(width=width, height=height, featureless_windows=list(range(1, len(boxes))))
    return out


class Model:
    def __init__(self):
        self.metadata = {"classifier_kind": "bioclip-margin-cuda-v1"}
        self.calls = 0

    def profile_metadata(self, scope, proposer=None):
        return {**self.metadata, "scope": scope, "proposer": proposer}

    def frame(self, encoded):
        self.calls += 1
        import io

        from PIL import Image

        with Image.open(io.BytesIO(encoded)) as image:
            return score(*image.size)

    def regions(self, views):
        self.calls += 1
        return {name: score() for name in views}


def test_frame_native_scores_retry_and_changed_source_refusal(tmp_path):
    manifest, _ = corpus(tmp_path)
    model = Model()
    output = tmp_path / "margin.json"
    result = classify_margin_batch(manifest, tmp_path, output, model)
    assert result["predictions"][0]["scores"]["species"][0]["margin"] == -0.2
    assert "topk" not in result["predictions"][0]
    calls = model.calls
    assert classify_margin_batch(manifest, tmp_path, output, model) == result
    assert model.calls == calls
    with pytest.raises(ValueError, match="pinned"):
        classify_margin_batch(
            manifest, tmp_path, tmp_path / "bad.json", model, expected_manifest_sha256="0" * 64
        )
    assert model.calls == calls


def test_region_three_view_cache_mask_and_source_bindings(tmp_path):
    manifest, proposals, _ = inputs(tmp_path)
    model = Model()
    output = tmp_path / "margin.json"
    result = classify_margin_batch(
        manifest,
        tmp_path,
        output,
        model,
        scope="regions",
        proposals=proposals,
        proposer_kind="sam3",
    )
    views = result["predictions"][0]["regions"][0]["views"]
    assert set(views) == {"tight", "masked", "context"}
    assert (
        classify_margin_batch(
            manifest,
            tmp_path,
            output,
            model,
            scope="regions",
            proposals=proposals,
            proposer_kind="sam3",
        )
        == result
    )
    assert model.calls == 1
    with pytest.raises(ValueError, match="pinned"):
        classify_margin_batch(
            manifest,
            tmp_path,
            tmp_path / "bad.json",
            model,
            scope="regions",
            proposals=proposals,
            proposer_kind="sam3",
            expected_proposals_sha256="0" * 64,
        )
    assert model.calls == 1


def test_interrupted_batch_reuses_completed_photos(tmp_path):
    manifest, _ = corpus(tmp_path)
    from weedz.discovery.inference import file_sha256
    from weedz.manifest import read_manifest, write_manifest

    first = read_manifest(manifest, file_sha256(manifest))[0]
    write_manifest(manifest, [first, first.model_copy(update={"id": "test:2", "source_id": "2"})])
    model = Model()
    original = model.frame

    def interrupted(encoded):
        if model.calls == 1:
            raise RuntimeError("interrupted")
        return original(encoded)

    model.frame = interrupted
    with pytest.raises(RuntimeError):
        classify_margin_batch(manifest, tmp_path, tmp_path / "partial.json", model)
    assert model.calls == 1
    model.frame = original
    result = classify_margin_batch(manifest, tmp_path, tmp_path / "partial.json", model)
    assert model.calls == len(result["predictions"])


def test_changed_raw_comparison_cache_is_refused_even_with_recomputed_digest(tmp_path):
    import json

    from weedz.segmentation.artifacts import digest

    manifest, _ = corpus(tmp_path)
    model = Model()
    output = tmp_path / "scores.json"
    result = classify_margin_batch(manifest, tmp_path, output, model)
    result["predictions"][0]["scores"]["window_similarities"][0][0] = 0.8
    result["result_sha256"] = digest({k: v for k, v in result.items() if k != "result_sha256"})
    output.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="aggregation"):
        classify_margin_batch(manifest, tmp_path, output, model)
    assert model.calls == 1


def test_lazy_metadata_drift_cannot_poison_partial_photo_cache(tmp_path):
    manifest, _ = corpus(tmp_path)
    model = Model()
    original = model.frame

    def drift(encoded):
        result = original(encoded)
        model.metadata["changed"] = "during inference"
        return result

    model.frame = drift
    with pytest.raises(ValueError, match="metadata"):
        classify_margin_batch(manifest, tmp_path, tmp_path / "scores.json", model)
    assert not list(tmp_path.glob("*.parts/*.json"))


def test_cached_nonwinning_window_geometry_is_still_source_bound(tmp_path):
    import json

    from weedz.segmentation.artifacts import digest

    manifest, _ = corpus(tmp_path)
    model = Model()
    output = tmp_path / "scores.json"
    result = classify_margin_batch(manifest, tmp_path, output, model)
    result["predictions"][0]["scores"]["window_boxes"][-1] = [0, 0, 999, 999]
    result["result_sha256"] = digest({k: v for k, v in result.items() if k != "result_sha256"})
    output.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="geometry"):
        classify_margin_batch(manifest, tmp_path, output, model)
    assert model.calls == 1


def test_final_cache_retry_reseals_after_postwrite_failure(tmp_path, monkeypatch):
    from weedz.classification import bioclip_batches

    manifest, _ = corpus(tmp_path)
    model = Model()
    output = tmp_path / "scores.json"
    original = bioclip_batches.seal_file
    attempts = []

    def fail_once(root, path):
        if path == output:
            attempts.append(path)
            if len(attempts) == 1:
                raise OSError("post-write sync failure")
        return original(root, path)

    monkeypatch.setattr(bioclip_batches, "seal_file", fail_once)
    with pytest.raises(OSError):
        classify_margin_batch(manifest, tmp_path, output, model)
    assert output.is_file()
    classify_margin_batch(manifest, tmp_path, output, model)
    assert len(attempts) == 2
    assert model.calls == 1


def test_cached_featureless_eligibility_is_bound_to_verified_pixels(tmp_path):
    import json

    from weedz.segmentation.artifacts import digest

    manifest, _ = corpus(tmp_path)
    model = Model()
    output = tmp_path / "scores.json"
    result = classify_margin_batch(manifest, tmp_path, output, model)
    assert result["predictions"][0]["scores"]["featureless_windows"]
    result["predictions"][0]["scores"]["featureless_windows"] = []
    result["result_sha256"] = digest({k: v for k, v in result.items() if k != "result_sha256"})
    output.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="eligibility"):
        classify_margin_batch(manifest, tmp_path, output, model)
    assert model.calls == 1
