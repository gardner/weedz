import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image
from test_contract import sample

from weedz.classification.batch import classify_batch
from weedz.contract import Sample
from weedz.manifest import write_manifest


class Classifier:
    metadata = {"model": "test classifier", "weights_sha256": "a" * 64}
    calls = 0

    def predict(self, images, top_k=5):
        self.calls += 1
        return [
            [
                {
                    "taxon": "Example species",
                    "score": 0.4,
                    "score_kind": "closed_set_softmax_uncalibrated",
                }
            ]
            for _ in images
        ]


def corpus(tmp_path):
    image = tmp_path / "image.png"
    Image.new("RGB", (32, 32), "green").save(image)
    sha = hashlib.sha256(image.read_bytes()).hexdigest()
    record = Sample.model_validate(
        sample(
            media={"uri": "image.png", "sha256": sha, "width": 32, "height": 32},
            tasks=["inference"],
            annotations=[],
        )
    )
    manifest = tmp_path / "samples.jsonl"
    write_manifest(manifest, [record])
    return manifest, image


def test_matching_completed_batch_resumes_without_new_model_calls(tmp_path):
    manifest, _ = corpus(tmp_path)
    model = Classifier()
    out = tmp_path / "predictions.json"
    first = classify_batch(manifest, tmp_path, out, model)
    second = classify_batch(manifest, tmp_path, out, model)
    assert first == second
    assert model.calls == 1
    assert first["predictions"][0]["source_id"] == "test:1"
    assert "annotations" not in first


def test_cache_never_hides_changed_source_pixels(tmp_path):
    manifest, image = corpus(tmp_path)
    model = Classifier()
    out = tmp_path / "predictions.json"
    classify_batch(manifest, tmp_path, out, model)
    image.write_bytes(b"changed pixels")
    with pytest.raises(ValueError, match="checksum"):
        classify_batch(manifest, tmp_path, out, model)
    assert model.calls == 1


def test_tiled_predictions_keep_regions_without_claiming_masks(tmp_path):
    manifest, _ = corpus(tmp_path)
    result = classify_batch(manifest, tmp_path, tmp_path / "tiles.json", Classifier(), "tiles")
    row = result["predictions"][0]
    assert len(row["views"]) > 1
    assert all("box" in view and "mask" not in view for view in row["views"])
    assert row["topk"][0]["score_kind"] == "maximum_closed_set_softmax_across_views_uncalibrated"


def test_path_replacement_cannot_change_pixels_after_the_checksum_check(tmp_path, monkeypatch):
    manifest, image = corpus(tmp_path)
    original_open = Image.open

    def replace_before_decode(source, *args, **kwargs):
        if isinstance(source, (str, Path)):
            Image.new("RGB", (32, 32), "red").save(image)
        return original_open(source, *args, **kwargs)

    class Inspect(Classifier):
        def predict(self, images, top_k=5):
            assert images[0].getpixel((0, 0)) == (0, 128, 0)
            return super().predict(images, top_k)

    monkeypatch.setattr("weedz.classification.batch.Image.open", replace_before_decode)
    classify_batch(manifest, tmp_path, tmp_path / "out.json", Inspect())


def test_cached_prediction_bytes_cannot_be_changed_without_detection(tmp_path):
    manifest, _ = corpus(tmp_path)
    out = tmp_path / "predictions.json"
    model = Classifier()
    classify_batch(manifest, tmp_path, out, model)
    changed = json.loads(out.read_text())
    changed["predictions"][0]["topk"][0]["score"] = 0.9
    out.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="checksum"):
        classify_batch(manifest, tmp_path, out, model)
    assert model.calls == 1


def test_wrong_geometry_and_noncanonical_media_are_refused(tmp_path):
    manifest, image = corpus(tmp_path)
    record = Sample.model_validate_json(manifest.read_text())
    write_manifest(
        manifest,
        [record.model_copy(update={"media": record.media.model_copy(update={"width": 31})})],
    )
    with pytest.raises(ValueError, match="geometry"):
        classify_batch(manifest, tmp_path, tmp_path / "bad-size.json", Classifier())
    jpeg = image.with_suffix(".jpg")
    Image.new("RGB", (32, 32), "green").save(jpeg)
    replacement = record.media.model_copy(
        update={"uri": jpeg.name, "sha256": hashlib.sha256(jpeg.read_bytes()).hexdigest()}
    )
    write_manifest(manifest, [record.model_copy(update={"media": replacement})])
    with pytest.raises(ValueError, match="canonical"):
        classify_batch(manifest, tmp_path, tmp_path / "bad-format.json", Classifier())


def test_legacy_results_need_an_explicit_verified_reference_and_complete_rows(tmp_path):
    manifest, _ = corpus(tmp_path)
    out = tmp_path / "predictions.json"
    model = Classifier()
    result = classify_batch(manifest, tmp_path, out, model)
    result.pop("result_sha256")
    out.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="verified legacy"):
        classify_batch(manifest, tmp_path, out, model)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    adopted = classify_batch(manifest, tmp_path, out, model, verified_existing_sha256=sha)
    assert adopted == result and model.calls == 1
    result["predictions"] = []
    out.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="Incomplete"):
        classify_batch(
            manifest,
            tmp_path,
            out,
            model,
            verified_existing_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
        )


def test_overlapping_retry_reuses_a_completed_result_instead_of_overwriting_it(tmp_path):
    manifest, _ = corpus(tmp_path)
    out = tmp_path / "predictions.json"
    first = classify_batch(manifest, tmp_path, out, Classifier())
    encoded = out.read_bytes()
    out.unlink()

    class Late(Classifier):
        def predict(self, images, top_k=5):
            out.write_bytes(encoded)  # The other attempt commits while this inference is running.
            return [
                [
                    {
                        "taxon": "Different result",
                        "score": 0.5,
                        "score_kind": "closed_set_softmax_uncalibrated",
                    }
                ]
                for _ in images
            ]

    actual = classify_batch(manifest, tmp_path, out, Late())
    assert actual == first
    assert out.read_bytes() == encoded


def test_metadata_after_pixel_chunks_is_not_accepted_as_canonical_media(tmp_path):
    import struct
    import zlib

    manifest, image = corpus(tmp_path)
    encoded = image.read_bytes()
    chunk = b"tEXt" + b"private-location\0must-not-be-published"
    payload = struct.pack(">I", len(chunk) - 4) + chunk + struct.pack(">I", zlib.crc32(chunk))
    image.write_bytes(encoded[:-12] + payload + encoded[-12:])
    record = Sample.model_validate_json(manifest.read_text())
    media = record.media.model_copy(
        update={"sha256": hashlib.sha256(image.read_bytes()).hexdigest()}
    )
    write_manifest(manifest, [record.model_copy(update={"media": media})])
    with pytest.raises(ValueError, match="canonical"):
        classify_batch(manifest, tmp_path, tmp_path / "out", Classifier())


@pytest.mark.parametrize("damage", ["missing_views", "wrong_box", "wrong_aggregate"])
def test_legacy_tile_adoption_requires_reproducible_per_view_evidence(tmp_path, damage):
    manifest, _ = corpus(tmp_path)
    output = tmp_path / "tiles.json"
    result = classify_batch(manifest, tmp_path, output, Classifier(), "tiles")
    result.pop("result_sha256")
    row = result["predictions"][0]
    if damage == "missing_views":
        row.pop("views")
    elif damage == "wrong_box":
        row["views"][0]["box"] = [0, 0, 1, 1]
    else:
        row["topk"][0]["score"] = 0.9
    output.write_text(json.dumps(result))
    with pytest.raises(ValueError, match="[Tt]il|[Aa]ggregat"):
        classify_batch(
            manifest,
            tmp_path,
            output,
            Classifier(),
            "tiles",
            verified_existing_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
        )


@pytest.mark.parametrize("setting,value", [("TILE_FRACTION", 0.5), ("LETTERBOX", (0, 0, 0))])
def test_actual_tiling_policy_changes_create_a_new_pipeline_identity(
    tmp_path, monkeypatch, setting, value
):
    from weedz.discovery import inference

    manifest, _ = corpus(tmp_path)
    first = classify_batch(manifest, tmp_path, tmp_path / "one", Classifier(), "tiles")
    monkeypatch.setattr(inference, setting, value)
    second = classify_batch(manifest, tmp_path, tmp_path / "two", Classifier(), "tiles")
    assert first["model_version"] != second["model_version"]
