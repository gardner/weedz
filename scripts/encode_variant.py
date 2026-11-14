"""Encode pre-processed windows with one image-tower artefact, alone in its process (#52).

compare_optimised.py runs this once per variant so each one's peak memory is its own.
Windows arrive already cropped, letterboxed and normalised (one <photo id>.npy per
photo), so only the image tower is timed, as it would run on a device. Prints one JSON
line: per-photo encoding seconds plus baseline and peak resident memory.

Usage:
  uv run python scripts/encode_variant.py --kind onnx --artefact tower.onnx \
      --pixels <dir> --ids <ids.json> --out embeddings.npz
"""

import argparse
import json
import resource
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import numpy as np

Encode = Callable[[np.ndarray], np.ndarray]
# As in Screener.load: four CPU threads and up to 16 windows per encoder call.
THREADS = 4
BATCH = 16


def peak_rss_bytes() -> int:
    """Peak resident memory of this process so far (Linux reports kilobytes)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024


def _torch_encoder(artefact: Path, threads: int) -> Encode:
    import torch

    torch.set_num_threads(threads)
    # The artefact is a whole module this benchmark saved itself, so unpickling is trusted.
    tower = torch.load(artefact, weights_only=False).eval()
    dtype = next(tower.parameters()).dtype

    def encode(pixels: np.ndarray) -> np.ndarray:
        with torch.inference_mode():
            return tower(torch.from_numpy(pixels).to(dtype)).float().numpy()

    return encode


def _onnx_encoder(artefact: Path, threads: int) -> Encode:
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(artefact), options, providers=["CPUExecutionProvider"])
    name = session.get_inputs()[0].name

    def encode(pixels: np.ndarray) -> np.ndarray:
        return np.asarray(session.run(None, {name: pixels})[0], dtype=np.float32)

    return encode


def load_encoder(kind: str, artefact: Path, threads: int = THREADS) -> Encode:
    loaders = {"torch": _torch_encoder, "onnx": _onnx_encoder}
    return loaders[kind](artefact, threads)


def encode_photos(
    encode: Encode, pixel_dir: Path, ids: list[str], batch: int = BATCH
) -> tuple[dict[str, np.ndarray], list[float]]:
    """Every photo's window embeddings and the seconds its windows took to encode.

    The first photo is encoded once untimed, so one-off start-up work is not billed to it.
    """
    if ids:
        encode(np.load(pixel_dir / f"{ids[0]}.npy")[:batch])
    embeddings, seconds = {}, []
    for pid in ids:
        pixels = np.load(pixel_dir / f"{pid}.npy")
        started = time.perf_counter()
        chunks = [encode(pixels[start : start + batch]) for start in range(0, len(pixels), batch)]
        seconds.append(time.perf_counter() - started)
        embeddings[pid] = np.concatenate(chunks)
    return embeddings, seconds


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Encode windows with one image tower")
    parser.add_argument("--kind", choices=["torch", "onnx"], required=True)
    parser.add_argument("--artefact", type=Path, required=True)
    parser.add_argument("--pixels", type=Path, required=True)
    parser.add_argument("--ids", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    # Import the runtime first, so the baseline holds the interpreter and runtime only.
    __import__("torch" if args.kind == "torch" else "onnxruntime")
    baseline = peak_rss_bytes()
    encode = load_encoder(args.kind, args.artefact)
    embeddings, seconds = encode_photos(encode, args.pixels, json.loads(args.ids.read_text()))
    np.savez(args.out, **cast(dict[str, Any], embeddings))
    stats = {"seconds": seconds, "baseline_rss_bytes": baseline, "peak_rss_bytes": peak_rss_bytes()}
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
