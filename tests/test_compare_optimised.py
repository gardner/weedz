"""The optimised-model parity benchmark: encoding in isolation and the committed file (#52).

Tiny stand-in image towers keep these tests offline; no screening model is downloaded.
"""

import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import numpy as np
import pytest
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


def test_a_child_does_not_inherit_its_parents_peak_memory(tmp_path: Path) -> None:
    """Linux keeps ru_maxrss across fork and exec; the child must report its own peak."""
    save_onnx(tiny_tower(), tmp_path / "tower.onnx")
    pixels = pixel_dir(tmp_path, {"a": 1})
    ballast = np.ones(800_000_000 // 8)  # the parent touches about 800 MB
    stats = script.encode_in_process(
        "onnx", tmp_path / "tower.onnx", pixels, ["a"], tmp_path / "out.npz"
    )
    assert ballast.sum() > 0
    assert stats["peak_rss_bytes"] < 500_000_000


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


def test_an_interrupted_artefact_write_leaves_nothing_to_reuse(tmp_path: Path) -> None:
    target = tmp_path / "visual.onnx"

    def interrupted(path: Path) -> None:
        path.write_bytes(b"partial")
        raise OSError("disk full")

    with pytest.raises(OSError):
        script.write_atomically(target, interrupted)
    assert not target.exists()
    script.write_atomically(target, lambda path: path.write_bytes(b"whole"))
    assert target.read_bytes() == b"whole"
    assert [item.name for item in tmp_path.iterdir()] == ["visual.onnx"]


def test_artefacts_are_cached_per_weights_libraries_and_export_settings(tmp_path: Path) -> None:
    metadata = {"model_key": "bioclip-2", "revision": "r", "weights_sha256": "w" * 64}
    versions = {"torch": "2.15.0", "onnxruntime": "1.32.0"}
    folder = script.artefact_folder(tmp_path, metadata, versions)
    assert folder.parent == tmp_path / "bioclip-2"
    assert folder == script.artefact_folder(tmp_path, dict(metadata), dict(versions))
    repinned = metadata | {"weights_sha256": "v" * 64}
    upgraded = versions | {"onnxruntime": "1.33.0"}
    assert script.artefact_folder(tmp_path, repinned, versions) != folder
    assert script.artefact_folder(tmp_path, metadata, upgraded) != folder
    fingerprint = json.loads((folder / "provenance.json").read_text())
    assert fingerprint["weights_sha256"] == "w" * 64
    assert fingerprint["export"] == script.EXPORT


def test_a_single_file_artefact_records_the_hash_a_bundle_gate_checks(tmp_path: Path) -> None:
    single = tmp_path / "visual-fp16.pt"
    single.write_bytes(b"weights")
    assert script.artefact_sha256(single) == hashlib.sha256(b"weights").hexdigest()
    split = tmp_path / "visual.onnx"
    split.write_bytes(b"graph")
    (tmp_path / "visual.onnx.data").write_bytes(b"external weights")
    assert script.artefact_sha256(split) is None, "an artefact in several files ships as none"


def test_every_artefact_records_how_it_runs_so_a_bundle_need_not_be_told() -> None:
    assert set(script.RUNTIME) == set(script.ARTEFACTS)
    assert script.RUNTIME["fp16"] == {
        "format": "torch",
        "precision": "fp16",
        "input_dtype": "float16",
    }
    assert script.RUNTIME["int8"]["input_dtype"] == "float32"


def test_an_onnx_graph_whose_weights_live_elsewhere_records_no_hash(tmp_path: Path) -> None:
    """External data written under another name (e.g. the exporter's partial name) is
    found from the graph's own references, not from file names."""
    import onnx
    from onnx import TensorProto, helper, numpy_helper

    weight = numpy_helper.from_array(np.ones((2, 2), dtype=np.float32), "weight")
    graph = helper.make_graph(
        [helper.make_node("MatMul", ["pixels", "weight"], ["embedding"])],
        "tower",
        [helper.make_tensor_value_info("pixels", TensorProto.FLOAT, [1, 2])],
        [helper.make_tensor_value_info("embedding", TensorProto.FLOAT, [1, 2])],
        [weight],
    )
    path = tmp_path / "visual.onnx"
    onnx.save_model(
        helper.make_model(graph),
        str(path),
        save_as_external_data=True,
        location="visual.partial.onnx.data",
        size_threshold=0,
    )
    assert script.artefact_sha256(path) is None
    inline = tmp_path / "inline.onnx"
    onnx.save_model(helper.make_model(graph), str(inline))
    assert script.artefact_sha256(inline) == hashlib.sha256(inline.read_bytes()).hexdigest()
