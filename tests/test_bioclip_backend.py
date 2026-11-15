"""Backend selection is explicit; historical CPU scores/caches keep their contract."""

import pytest
import torch
from pydantic import ValidationError

from weedz.discovery import cli
from weedz.discovery.inference import MODELS, Screener
from weedz.discovery.records import RunSpec
from weedz.discovery.score_meaning import pin_meaning


def test_backend_selection_and_historical_default():
    assert RunSpec.from_saved({}).screening_backend == "cpu"
    assert cli.parse(["discover"]).screening_backend == "cpu"
    assert (
        cli.parse(["discover", "--screening-backend", "cuda-fp32-v1"]).screening_backend
        == "cuda-fp32-v1"
    )
    with pytest.raises(ValidationError):
        RunSpec.model_validate({"screening_backend": "automatic"})


def test_cuda_refuses_unavailable_device_before_download(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="CUDA"):
        Screener.load(backend="cuda-fp32-v1")


def test_gpu_cannot_borrow_cpu_pilot_score_meaning():
    metadata = {
        "model_key": "bioclip-2",
        "revision": MODELS["bioclip-2"]["revision"],
        "ranking_revision": 4,
        "calibrated": False,
    }
    assert pin_meaning(None, metadata)["score_meaning"] is not None
    gpu = {**metadata, "backend_profile": "cuda-fp32-v1", "device": "cuda:0"}
    assert pin_meaning(None, gpu)["score_meaning"] is None


def test_cuda_encoder_places_inputs_and_returns_cpu_float32(monkeypatch):
    from contextlib import contextmanager

    from weedz.discovery.encoder_backend import CudaEncoder

    events = []

    class Tensor:
        def to(self, *args, **kwargs):
            events.append(("tensor", args, kwargs))
            return self

    class Model:
        def float(self):
            events.append("float")
            return self

        def to(self, device):
            events.append(("model", device))
            return self

        def eval(self):
            return self

        def encode_image(self, value, *, normalize):
            assert normalize
            return value

        encode_text = encode_image

    @contextmanager
    def precision(runtime, device):
        events.append(("precision", device))
        yield

    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "get_device_name", lambda _: "test GPU")
    monkeypatch.setattr("weedz.discovery.encoder_backend.fp32_math", precision)
    encoder = CudaEncoder(Model())
    encoder.encode_image(Tensor(), normalize=True)
    encoder.encode_text(Tensor(), normalize=True)
    assert events[:2] == ["float", ("model", "cuda:0")]
    assert ("tensor", (), {"device": "cuda:0", "dtype": torch.float32}) in events
    assert ("tensor", ("cuda:0",), {}) in events  # tokenizer IDs keep integer dtype
    assert events.count(("tensor", (), {"device": "cpu", "dtype": torch.float32})) == 2
    assert events.count(("precision", "cuda:0")) == 2
    assert encoder.metadata["math_policy"]["autocast"] is False


def test_gpu_cosine_disables_ambient_cpu_autocast():
    from types import SimpleNamespace

    from weedz.discovery.encoder_backend import cosine_scores

    screener = SimpleNamespace(torch=torch, metadata={"backend_profile": "cuda-fp32-v1"})
    features = torch.tensor([[0.1234567, 0.9876543]])
    text = torch.tensor([[0.7654321, 0.2345678]])
    expected = (features @ text.T).numpy()
    with torch.autocast("cpu", dtype=torch.bfloat16):
        actual = cosine_scores(screener, features, text)
    assert actual.dtype.name == "float32"
    assert (actual == expected).all()


def test_gpu_profile_cannot_reuse_cpu_embedding_cache(tmp_path, monkeypatch):
    import huggingface_hub
    import open_clip
    from test_discovery_inference import FakeEncoder

    from weedz.discovery import encoder_backend

    (tmp_path / MODELS["bioclip"]["weights"]).write_bytes(b"test weights")
    monkeypatch.setattr(huggingface_hub, "snapshot_download", lambda *a, **kw: str(tmp_path))
    monkeypatch.setattr(
        open_clip,
        "create_model_and_transforms",
        lambda *a: (FakeEncoder(), None, lambda _: torch.zeros(3)),
    )
    monkeypatch.setattr(open_clip, "get_tokenizer", lambda _: lambda prompts: prompts)
    monkeypatch.setattr(open_clip, "get_model_preprocess_cfg", lambda _: {})
    monkeypatch.setattr(encoder_backend, "require_backend", lambda _: None)

    def gpu(model):
        model.metadata = {"backend_profile": "cuda-fp32-v1", "device": "cuda:0"}
        return model

    monkeypatch.setattr(encoder_backend, "CudaEncoder", gpu)
    cpu = Screener.load(tmp_path / "embeddings")
    cuda = Screener.load(tmp_path / "embeddings", backend="cuda-fp32-v1")
    assert cpu.cache_path(b"image", [(0, 0, 1, 1)]) != cuda.cache_path(b"image", [(0, 0, 1, 1)])
    assert "backend_profile" not in cpu.metadata
    assert cuda.metadata["backend_profile"] == "cuda-fp32-v1"
