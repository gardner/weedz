"""The optimised-model parity benchmark: encoding in isolation and the committed file (#52).

Tiny stand-in image towers keep these tests offline; no screening model is downloaded.
"""

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import torch

from weedz.discovery.parity import THRESHOLDS


def load_script(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).parents[1] / "scripts" / f"{name}.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


encoder = load_script("encode_variant")
script = load_script("compare_optimised")


def tiny_tower() -> torch.nn.Module:
    torch.manual_seed(0)
    return torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(12, 4)).eval()


def pixel_dir(tmp_path: Path, windows: dict[str, int]) -> Path:
    folder = tmp_path / "pixels"
    folder.mkdir()
    rng = np.random.default_rng(0)
    for pid, count in windows.items():
        np.save(folder / f"{pid}.npy", rng.normal(size=(count, 3, 2, 2)).astype(np.float32))
    return folder


def save_onnx(module: torch.nn.Module, path: Path) -> None:
    torch.onnx.export(
        module,
        (torch.zeros(1, 3, 2, 2),),
        str(path),
        input_names=["pixels"],
        output_names=["embedding"],
        dynamic_axes={"pixels": {0: "batch"}, "embedding": {0: "batch"}},
        dynamo=False,
    )


def test_torch_and_onnx_artefacts_encode_every_window_alike(tmp_path: Path) -> None:
    tower = tiny_tower()
    torch.save(tower, tmp_path / "tower.pt")
    save_onnx(tower, tmp_path / "tower.onnx")
    pixels = pixel_dir(tmp_path, {"a": 3, "b": 20})
    found = {}
    for kind, artefact in [("torch", "tower.pt"), ("onnx", "tower.onnx")]:
        encode = encoder.load_encoder(kind, tmp_path / artefact, threads=1)
        found[kind], seconds = encoder.encode_photos(encode, pixels, ["a", "b"], batch=16)
        assert [found[kind][pid].shape for pid in "ab"] == [(3, 4), (20, 4)]
        assert len(seconds) == 2 and all(s >= 0 for s in seconds)
    np.testing.assert_allclose(found["torch"]["b"], found["onnx"]["b"], atol=1e-5)


def test_encoding_runs_as_its_own_process_and_reports_memory(tmp_path: Path) -> None:
    save_onnx(tiny_tower(), tmp_path / "tower.onnx")
    pixels = pixel_dir(tmp_path, {"a": 2})
    out = tmp_path / "out.npz"
    stats = script.encode_in_process("onnx", tmp_path / "tower.onnx", pixels, ["a"], out)
    assert np.load(out)["a"].shape == (2, 4)
    assert stats["peak_rss_bytes"] >= stats["baseline_rss_bytes"] > 0
    assert len(stats["seconds"]) == 1


def test_results_score_normalised_embeddings_against_each_photos_text() -> None:
    embeddings = {"a": np.array([[3.0, 4.0], [0.0, 2.0]])}
    texts = {"a": np.array([[1.0, 0.0], [0.0, 1.0]])}
    layout = {"a": {"width": 10, "height": 10, "featureless_windows": [1]}}
    found = script.results(embeddings, texts, layout)
    np.testing.assert_allclose(found["a"]["window_similarities"], [[0.6, 0.8], [0.0, 1.0]])
    assert found["a"]["width"] == 10
    assert found["a"]["featureless_windows"] == [1]


def variant(passed: bool) -> dict[str, Any]:
    return {
        "model": "imageomics/bioclip-2",
        "description": "d",
        "cost": {"artefact_mb": 1.0},
        "parity": {"passed": passed, "checks": {}, "thresholds": THRESHOLDS},
    }


def test_document_keeps_provenance_thresholds_and_caveats() -> None:
    reference = {"model": "m", "model_key": "k", "revision": "r", "weights_sha256": "w", "x": 1}
    found = script.document(
        {"onnx-int8": variant(True), "bioclip-vit-b16": variant(False)},
        reference,
        {"artefact_mb": 2.0},
        {"run": "nelson", "pilot_photos": 30, "lookalike_photos": 39},
        {"cpu": "test cpu", "threads": 4},
        "2026-11-14",
    )
    assert found["issue"] == "https://github.com/gardner/weedz/issues/52"
    assert found["reference"]["model"] == {key: reference[key] for key in script.PROVENANCE}
    assert found["reference"]["cost"] == {"artefact_mb": 2.0}
    assert found["thresholds"] == THRESHOLDS
    assert found["machine"]["cpu"] == "test cpu"
    assert "not phone latency" in found["caveats"]
    assert "onnx-int8" in found["conclusion"] and "bioclip-vit-b16" in found["conclusion"]
    # Each variant's report does not repeat the shared thresholds.
    assert "thresholds" not in found["variants"]["onnx-int8"]["parity"]
    json.dumps(found)


def test_conclusion_names_passing_and_failing_variants() -> None:
    text = script.conclusion({"good": variant(True), "bad": variant(False)})
    assert "Kept parity: good." in text
    assert "Failed parity: bad." in text
    assert "Kept parity: none." in script.conclusion({"bad": variant(False)})
