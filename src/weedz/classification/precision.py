"""Explicit FP32 execution isolated from ambient autocast and legacy TF32 flags."""

from collections.abc import Iterator
from contextlib import contextmanager
from threading import RLock
from typing import Any

MATH_POLICY = {"cuda_matmul_tf32": False, "cudnn_tf32": False, "autocast": False}
_LOCK = RLock()


@contextmanager
def fp32_math(torch: Any, device: str) -> Iterator[None]:
    # CUDA backend flags are process-global. GPU workers isolate SAM and classifiers
    # in separate processes; this lock also serializes concurrent classifier calls.
    with _LOCK:
        previous = (torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32)
        try:
            # SAM3 uses this legacy API too; PyTorch forbids mixing it with the new one.
            torch.backends.cuda.matmul.allow_tf32 = False
            torch.backends.cudnn.allow_tf32 = False
            with torch.autocast(device_type=device.split(":")[0], enabled=False):
                yield
        finally:
            torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32 = previous
