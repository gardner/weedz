"""Measured transform provenance is portable and follows the prepared model."""

import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_compare_optimised import script

from weedz.bundles.text_table import preprocessing_sha256
from weedz.discovery.inference import Screener

CONFIG: dict[str, Any] = {"size": (224, 224), "mean": (0.1, 0.2, 0.3)}


def test_transform_hash_uses_the_same_portable_canonical_bytes_as_the_sidecar() -> None:
    expected = b'{"mean":["0.1","0.2","0.3"],"size":[224,224]}'
    assert preprocessing_sha256(CONFIG) == hashlib.sha256(expected).hexdigest()
    saved = json.loads('{"mean":["0.1","0.2","0.3"],"size":[224,224]}')
    assert preprocessing_sha256(saved) == preprocessing_sha256(CONFIG)
    assert preprocessing_sha256(CONFIG | {"size": [512, 512]}) != preprocessing_sha256(CONFIG)


def model_metadata() -> dict[str, str]:
    return {
        "model": "imageomics/bioclip-2",
        "model_key": "bioclip-2",
        "revision": "r",
        "weights_sha256": "a" * 64,
    }


def test_prepare_binds_the_loaded_model_config_to_metadata_and_artifact_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = dict(CONFIG)
    model = SimpleNamespace(visual=object())
    screener = SimpleNamespace(model=model, metadata=model_metadata())
    monkeypatch.setattr(Screener, "load", classmethod(lambda cls, **kwargs: screener))
    monkeypatch.setitem(
        sys.modules,
        "open_clip",
        SimpleNamespace(
            __version__="test",
            get_model_preprocess_cfg=lambda value: config if value is model else None,
        ),
    )
    monkeypatch.setattr(script, "export_artefacts", lambda *args: None)
    first = script.prepare("bioclip-2", [], tmp_path, set())
    expected = preprocessing_sha256(config)
    assert first["metadata"]["preprocessing_sha256"] == expected
    provenance = json.loads((first["folder"] / "provenance.json").read_text())
    assert provenance["preprocessing_sha256"] == expected
    config["size"] = [512, 512]
    second = script.prepare("bioclip-2", [], tmp_path, set())
    assert second["folder"] != first["folder"]
    assert "preprocessing_sha256" not in screener.metadata


def test_run_records_each_measured_models_transform_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata = model_metadata() | {"preprocessing_sha256": preprocessing_sha256(CONFIG)}
    monkeypatch.setattr(script, "collect_photos", lambda args: [])
    monkeypatch.setattr(script, "window_layout", lambda photos: {})
    monkeypatch.setattr(script, "prepare", lambda *args: {"metadata": metadata})
    monkeypatch.setattr(script, "measure", lambda *args: ({}, {}, "b" * 64))
    monkeypatch.setattr(script, "compare", lambda *args: {"passed": True, "checks": {}})
    monkeypatch.setattr(script, "machine", lambda: {})
    result = script.run(SimpleNamespace(variants=["onnx-fp32"], work=tmp_path, run="test"))
    assert (
        result["variants"]["onnx-fp32"]["preprocessing_sha256"] == metadata["preprocessing_sha256"]
    )
    assert result["reference"]["model"]["preprocessing_sha256"] == metadata["preprocessing_sha256"]
