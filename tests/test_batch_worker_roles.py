"""Segmentation imports must not mutate CUDA policy during classifier inference."""

import importlib.util
from pathlib import Path

import pytest


def runner():
    spec = importlib.util.spec_from_file_location(
        "batch_runner", Path(__file__).parents[1] / "scripts/run_batch_worker.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gpu_roles_cannot_share_one_process():
    module = runner()
    with pytest.raises(ValueError, match="separate processes"):
        module.worker_roles("segmentation,classification")
    assert module.worker_roles("control,classification") == ["control", "classification"]
    assert module.worker_roles("segmentation") == ["segmentation"]
    with pytest.raises(ValueError, match="explicit"):
        module.worker_roles("unknown")


def test_control_role_checks_optional_encoder_before_polling(monkeypatch):
    import builtins

    module = runner()
    original = builtins.__import__

    def unavailable(name, *args, **kwargs):
        if name.startswith("label_studio_sdk"):
            raise ImportError("Optional encoder is absent")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", unavailable)
    with pytest.raises(RuntimeError, match="uv sync --extra annotation"):
        module.worker_roles("control")
    assert module.worker_roles("publication") == ["publication"]
