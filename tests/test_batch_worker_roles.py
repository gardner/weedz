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


def test_worker_shutdown_drains_an_inflight_request(monkeypatch, tmp_path):
    import asyncio
    import signal
    from datetime import timedelta
    from types import SimpleNamespace

    module = runner()
    events, handlers = [], {}

    async def connect(*_args, **_kwargs):
        return object()

    class DrainingWorker:
        def __init__(self, *_args, **kwargs):
            self.grace = kwargs.get("graceful_shutdown_timeout", timedelta())

        async def __aenter__(self):
            async def request():
                await asyncio.sleep(0.01)
                events.append("request completed")

            self.request = asyncio.create_task(request())
            handlers[signal.SIGTERM]()
            events.append("stop requested")
            return self

        async def __aexit__(self, *_args):
            await asyncio.wait_for(self.request, self.grace.total_seconds())
            events.append("drained")

    monkeypatch.setattr(module, "Client", SimpleNamespace(connect=connect))
    monkeypatch.setattr(module, "Worker", DrainingWorker)
    monkeypatch.setattr(module, "registry_from_config", lambda _: object())
    methods = {name: lambda *_: None for name in module.ROLES["classification"][1]}
    monkeypatch.setattr(module, "BatchActivities", lambda *_: SimpleNamespace(**methods))

    async def run():
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(
            loop, "add_signal_handler", lambda name, fn: handlers.update({name: fn})
        )
        await module.worker(
            SimpleNamespace(roles="classification", address="unused", namespace="unused"),
            {"artifact_root": str(tmp_path)},
        )

    asyncio.run(run())
    assert events == ["stop requested", "request completed", "drained"]
