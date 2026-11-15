"""Opt-in FP32 CUDA encoding, with CPU embeddings for the existing ranking code."""

from contextlib import nullcontext
from typing import Any

from weedz.classification.precision import MATH_POLICY, fp32_math

PROFILE = "cuda-fp32-v1"


def require_backend(backend: str) -> None:
    if backend not in {"cpu", PROFILE}:
        raise ValueError(f"Unsupported BioCLIP backend: {backend}")
    if backend == PROFILE:
        import torch

        if not torch.cuda.is_available():
            raise RuntimeError("cuda-fp32-v1 requires a CUDA-enabled Torch runtime and GPU")


class CudaEncoder:
    """Move the resident model once; never expose device-dependent cache tensors."""

    def __init__(self, model: Any) -> None:
        import torch

        require_backend(PROFILE)
        self.torch = torch
        self.model = model.float().to("cuda:0").eval()
        self.metadata = {
            "backend_profile": PROFILE,
            "device": "cuda:0",
            "scoring_device": "cpu",
            "precision": "float32",
            "math_policy": dict(MATH_POLICY),
            "cuda": torch.version.cuda,
            "cudnn": torch.backends.cudnn.version(),
            "gpu": torch.cuda.get_device_name(0),
            "numpy": __import__("numpy").__version__,
        }

    def eval(self) -> "CudaEncoder":
        self.model.eval()
        return self

    def encode_image(self, image: Any, *, normalize: bool) -> Any:
        with self.torch.inference_mode(), fp32_math(self.torch, "cuda:0"):
            return self.model.encode_image(
                image.to(device="cuda:0", dtype=self.torch.float32), normalize=normalize
            ).to(device="cpu", dtype=self.torch.float32)

    def encode_text(self, text: Any, *, normalize: bool) -> Any:
        with self.torch.inference_mode(), fp32_math(self.torch, "cuda:0"):
            return self.model.encode_text(text.to("cuda:0"), normalize=normalize).to(
                device="cpu", dtype=self.torch.float32
            )


def cosine_scores(screener: Any, features: Any, text: Any) -> Any:
    """Historical CPU execution stays unchanged; the GPU profile pins CPU FP32 scoring."""
    context = (
        fp32_math(screener.torch, "cpu")
        if screener.metadata.get("backend_profile") == PROFILE
        else nullcontext()
    )
    with screener.torch.inference_mode(), context:
        return (features.to(text.dtype) @ text.T).cpu().numpy()
