"""Generate the original Music3 instrumental score in an isolated GPU-0 environment."""

import argparse
import gc
import hashlib
import html
import importlib.metadata
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MODEL = "MiniMaxAI/MiniMax-Music3"
REVISION = "1b525ccb685ae809f33027c51c351eeb5833cf72"
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from demo_paths import outside_git  # noqa: E402

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
    ["[Intro]"] + ["[Instrumental]"] * 20 + ["[Bridge]"] + ["[Instrumental]"] * 8 + ["[Outro]"]
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
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Refusing to overwrite {path}")
        outside_git(path)


def provenance(seconds: float, seed: int, prompt: str = PROMPT) -> dict[str, object]:
    packages = ("torch", "diffusers", "transformers", "accelerate", "soundfile", "huggingface-hub")
    return {
        "model": MODEL,
        "model_revision": REVISION,
        "license_url": f"https://huggingface.co/{MODEL}/blob/{REVISION}/LICENSE",
        "prompt": prompt,
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


def load_pipeline() -> tuple[Any, Path]:
    """Load the cached pinned model once on reserved physical GPU 0."""
    if os.environ.get("CUDA_VISIBLE_DEVICES", "0") != "0":
        raise ValueError("This runner is restricted to physical GPU 0")
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"
    import torch
    from diffusers import ModularPipeline
    from huggingface_hub import snapshot_download

    if not torch.cuda.is_available():
        raise RuntimeError("Music3 requires CUDA; no CPU or other-GPU fallback is used")
    free, _ = torch.cuda.mem_get_info()
    if free < 26 * 1024**3:
        raise RuntimeError("GPU 0 has less than 26 GiB free; coordinate before loading the model")
    snapshot = snapshot_download(
        MODEL,
        revision=REVISION,
        local_files_only=True,
        allow_patterns=[f"{name}/*" for name in FOLDERS]
        + ["modular_model_index.json", "config.json", "LICENSE", "README.md"],
    )
    print(f"Loading pinned Music3 snapshot {REVISION} on GPU 0", flush=True)
    pipeline = ModularPipeline.from_pretrained(snapshot, local_files_only=True)
    pipeline.load_components(dtype=torch.bfloat16, local_files_only=True)
    pipeline.to("cuda")
    return pipeline, Path(snapshot)


def render_take(
    pipeline: Any,
    seconds: float,
    seed: int,
    output: Path,
    prompt: str = PROMPT,
    extra: dict[str, object] | None = None,
) -> dict[str, Any]:
    """Save one unprocessed take, retaining only the loaded model between calls."""
    import numpy as np
    import soundfile as sf
    import torch

    validate_request(seconds, seed, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata = provenance(seconds, seed, prompt) | (extra or {})
    metadata.update({"gpu": torch.cuda.get_device_name(0), "cuda": torch.version.cuda})
    output.with_suffix(".started.json").write_text(json.dumps(metadata, indent=2) + "\n")
    torch.cuda.reset_peak_memory_stats()
    started = time.monotonic()
    with torch.inference_mode():
        audio = pipeline(
            prompt=prompt,
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
    if rate != 44100:
        raise RuntimeError(f"Unexpected native sample rate: {rate}; no resampling is used")
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
            "signal_statistics": "Generated floats before PCM16 quantization; no normalization.",
            "peak_gpu_bytes": torch.cuda.max_memory_allocated(),
        }
    )
    output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2), flush=True)
    del audio, samples
    gc.collect()
    torch.cuda.empty_cache()
    return metadata


def generate(seconds: float, seed: int, output: Path) -> None:
    validate_request(seconds, seed, output)
    pipeline, _ = load_pipeline()
    render_take(pipeline, seconds, seed, output)


def load_presets(path: Path) -> list[dict[str, Any]]:
    items = json.loads(path.read_text())
    if not isinstance(items, list) or len(items) != 10:
        raise ValueError("Provide exactly ten audition presets")
    names, seeds, prompts = set(), set(), set()
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict) or set(item) != {
            "name",
            "title",
            "seed",
            "percussion",
            "variation",
            "prompt",
        }:
            raise ValueError("Invalid preset fields")
        name, seed, prompt = item["name"], item["seed"], item["prompt"]
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[0-9]{2}-[a-z0-9-]+", name)
            or not name.startswith(f"{index:02d}-")
            or name in names
        ):
            raise ValueError("Preset names must be unique ordered safe filenames")
        if type(seed) is not int or not 0 <= seed < 2**63 or seed in seeds:
            raise ValueError("Preset seeds must be unique nonnegative 64-bit integers")
        if (
            not isinstance(prompt, str)
            or not prompt.strip()
            or len(prompt) > 6000
            or prompt in prompts
        ):
            raise ValueError("Preset prompts must be distinct nonempty descriptions")
        if type(item["percussion"]) is not bool or any(
            not isinstance(item[key], str) or not item[key].strip()
            for key in ("title", "variation")
        ):
            raise ValueError("Invalid preset descriptions")
        names.add(name)
        seeds.add(seed)
        prompts.add(prompt)
    return items


def write_catalog(
    folder: Path, records: list[dict[str, Any]], presets: list[dict[str, Any]]
) -> None:
    (folder / "index.json").write_text(
        json.dumps(
            {
                "model": MODEL,
                "model_revision": REVISION,
                "completed": len(records),
                "requested": len(presets),
                "tracks": records,
                "disclosure": (
                    "Original AI-generated Music3 auditions; not human-composed performances."
                ),
                "duration_policy": (
                    "180-second upper bounds; no padding, looping, "
                    "assembly or narration processing."
                ),
            },
            indent=2,
        )
        + "\n"
    )
    playlist = ["#EXTM3U"]
    cards = []
    for record in records:
        filename = Path(record["output"]).name
        title = str(record["title"])
        duration = float(record["actual_seconds"])
        playlist += [f"#EXTINF:{duration:.3f},{title}", filename]
        cards.append(
            f"<article><h2>{html.escape(title)}</h2><p>{duration:.1f} seconds; "
            f"seed {record['seed']}; percussion requested: {record['percussion_requested']}</p>"
            f'<audio controls preload="none" src="{html.escape(filename)}"></audio>'
            f"<p>{html.escape(str(record['variation']))}</p>"
            "<details><summary>Full generation prompt</summary>"
            f"<p>{html.escape(str(record['prompt']))}</p></details></article>"
        )
    (folder / "auditions.m3u").write_text("\n".join(playlist) + "\n")
    (folder / "index.html").write_text(
        '<!doctype html><meta charset="utf-8"><title>Weedz music auditions</title>'
        "<style>body{font:18px system-ui;max-width:850px;margin:40px auto;padding:20px}"
        "article{border-top:1px solid #ccc;padding:18px 0}audio{width:100%}</style>"
        "<h1>Ten quiet documentary music auditions</h1>"
        "<p>Original AI-generated MiniMax Music3 music. "
        "Raw stereo PCM16 at native 44.1 kHz, no padding or looping. Durations are actual outputs. "
        "Prefer instrumental; occasional voice-like textures remain possible. "
        '<a href="LICENSE.txt">Full model license</a> · <a href="auditions.m3u">Playlist</a> · '
        '<a href="index.json">Complete provenance</a></p>' + "".join(cards)
    )


def generate_batch(seconds: float, folder: Path, preset_file: Path) -> None:
    presets = load_presets(preset_file)
    outputs = [folder / f"{item['name']}.wav" for item in presets]
    for item, output in zip(presets, outputs, strict=True):
        validate_request(seconds, item["seed"], output)
    for name in ("index.json", "index.html", "auditions.m3u", "LICENSE.txt", "presets.json"):
        path = folder / name
        outside_git(path)
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Refusing to overwrite {path}")
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(preset_file, folder / "presets.json")
    records: list[dict[str, Any]] = []
    write_catalog(folder, records, presets)
    pipeline, snapshot = load_pipeline()
    shutil.copyfile(snapshot / "LICENSE", folder / "LICENSE.txt")
    for item, output in zip(presets, outputs, strict=True):
        print(f"BEGIN {item['name']}: seed {item['seed']}, upper bound {seconds}s", flush=True)
        record = render_take(
            pipeline,
            seconds,
            item["seed"],
            output,
            item["prompt"],
            {
                "title": item["title"],
                "percussion_requested": item["percussion"],
                "variation": item["variation"],
                "preset_file_sha256": hashlib.sha256(preset_file.read_bytes()).hexdigest(),
                "batch_position": len(records) + 1,
                "batch_total": len(presets),
            },
        )
        records.append(record)
        write_catalog(folder, records, presets)
        print(
            f"COMPLETED {len(records)}/10: {output} ({record['actual_seconds']:.3f}s)", flush=True
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--batch-output", type=Path)
    parser.add_argument("--presets", type=Path, default=Path(__file__).with_name("auditions.json"))
    parser.add_argument("--seconds", type=float, default=180)
    parser.add_argument("--seed", type=int, default=112)
    args = parser.parse_args()
    if (args.output is None) == (args.batch_output is None):
        parser.error("Choose exactly one of --output or --batch-output")
    if args.batch_output is not None:
        generate_batch(args.seconds, args.batch_output, args.presets)
    else:
        generate(args.seconds, args.seed, args.output)


if __name__ == "__main__":
    main()
