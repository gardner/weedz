"""Generate the original Music3 instrumental score in an isolated GPU-0 environment."""

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

MODEL = "MiniMaxAI/MiniMax-Music3"
REVISION = "1b525ccb685ae809f33027c51c351eeb5833cf72"
ROOT = Path(__file__).resolve().parents[2]
FOLDERS = (
    "condition_encoder",
    "language_model",
    "rvq_depth_decoder",
    "scheduler",
    "tokenizer",
    "transformer",
    "vocoder",
)
LYRICS = "\n".join(
    (
        "[Intro]",
        "[Instrumental]",
        "[Instrumental]",
        "[Bridge]",
        "[Instrumental]",
        "[Instrumental]",
        "[Outro]",
    )
)
PROMPT = (
    "Global Metadata: Original instrumental conservation documentary underscore, approximately "
    "three minutes. Gentle ambient acoustic chamber music, 72 BPM, D major, warm, curious, "
    "reflective and quietly hopeful. A continuous evolving piece beneath spoken narration, "
    "with generous space and restrained dynamics, no dramatic swells or sudden accents. "
    "Vocal Details: Strictly instrumental. No singer, no vocals, no choir, no humming, "
    "no spoken words, no sung syllables. "
    "Arrangement: A simple original felt-piano motif, soft sustained strings, sparse acoustic "
    "guitar harmonics, warm unobtrusive bass and airy ambient textures. No heavy drums. "
    "Begin sparsely, develop gently through the middle, return to the opening motif and "
    "resolve softly at the end. Clear, intimate, natural production without harsh high frequencies."
)


def validate_request(seconds: float, seed: int, output: Path) -> None:
    if not math.isfinite(seconds) or not 0 < seconds <= 300:
        raise ValueError("Duration must be finite and between 0 and 300 seconds")
    if not 0 <= seed < 2**63:
        raise ValueError("Seed must fit a nonnegative signed 64-bit integer")
    if output.suffix.lower() != ".wav" or output.resolve().is_relative_to(ROOT):
        raise ValueError("Write a WAV outside the repository")
    for path in (output, output.with_suffix(".json"), output.with_suffix(".started.json")):
        if path.exists():
            raise FileExistsError(f"Refusing to overwrite {path}")


def provenance(seconds: float, seed: int) -> dict[str, object]:
    packages = ("torch", "diffusers", "transformers", "accelerate", "soundfile", "huggingface-hub")
    return {
        "model": MODEL,
        "model_revision": REVISION,
        "license_url": f"https://huggingface.co/{MODEL}/blob/{REVISION}/LICENSE",
        "prompt": PROMPT,
        "lyrics": LYRICS,
        "requested_seconds": seconds,
        "seed": seed,
        "flow_matching_steps": 30,
        "dtype": "bfloat16",
        "physical_gpu": 0,
        "packages": {name: importlib.metadata.version(name) for name in packages},
        "tool_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "created_at": datetime.now(UTC).isoformat(),
        "machine_generated": True,
        "limitations": "Instrumental control and exact duration are generative, not guarantees.",
    }


def generate(seconds: float, seed: int, output: Path) -> None:
    validate_request(seconds, seed, output)
    if os.environ.get("CUDA_VISIBLE_DEVICES", "0") != "0":
        raise ValueError("This runner is restricted to physical GPU 0")
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    import numpy as np
    import soundfile as sf
    import torch
    from diffusers import ModularPipeline
    from huggingface_hub import snapshot_download

    if not torch.cuda.is_available():
        raise RuntimeError("Music3 requires CUDA; no CPU or other-GPU fallback is used")
    free, _ = torch.cuda.mem_get_info()
    if free < 26 * 1024**3:
        raise RuntimeError("GPU 0 has less than 26 GiB free; coordinate before loading the model")
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = provenance(seconds, seed)
    metadata.update({"gpu": torch.cuda.get_device_name(0), "cuda": torch.version.cuda})
    output.with_suffix(".started.json").write_text(json.dumps(metadata, indent=2) + "\n")
    snapshot = snapshot_download(
        MODEL,
        revision=REVISION,
        allow_patterns=[f"{name}/*" for name in FOLDERS]
        + [
            "modular_model_index.json",
            "config.json",
            "LICENSE",
            "README.md",
        ],
        max_workers=8,
    )
    print(f"Loading pinned Music3 snapshot {REVISION} on GPU 0", flush=True)
    pipeline = ModularPipeline.from_pretrained(snapshot, local_files_only=True)
    pipeline.load_components(dtype=torch.bfloat16, local_files_only=True)
    pipeline.to("cuda")
    started = time.monotonic()
    with torch.inference_mode():
        audio = pipeline(
            prompt=PROMPT,
            lyrics=LYRICS,
            audio_duration=seconds,
            generator=torch.Generator("cuda").manual_seed(seed),
            num_inference_steps=30,
            output_type="pt",
            output="audios",
        )[0]
    samples = audio.float().cpu().numpy().T
    if samples.ndim != 2 or samples.shape[1] != 2 or not np.isfinite(samples).all():
        raise RuntimeError("Generated audio is not finite stereo data")
    rate = int(pipeline.sampling_rate)
    sf.write(output, samples, rate, subtype="PCM_16")
    metadata.update(
        {
            "sample_rate": rate,
            "channels": 2,
            "frames": len(samples),
            "actual_seconds": len(samples) / rate,
            "inference_seconds": time.monotonic() - started,
            "peak": float(np.max(np.abs(samples))),
            "rms": float(np.sqrt(np.mean(samples**2))),
            "samples_at_full_scale_fraction": float(np.mean(np.abs(samples) >= 1)),
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "output": str(output.resolve()),
            "subtype": "PCM_16",
            "postprocessing": "none",
            "peak_gpu_bytes": torch.cuda.max_memory_allocated(),
        }
    )
    output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=180)
    parser.add_argument("--seed", type=int, default=112)
    args = parser.parse_args()
    generate(args.seconds, args.seed, args.output)


if __name__ == "__main__":
    main()
