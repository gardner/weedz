"""Does an optimised image tower still screen like the validated reference? (#52, #51)

Usage:
  uv run python scripts/compare_optimised.py --pilot-dir <scratch copy of data/pilot> \
      --run nelson-tasman-3e62ad801459 --lookalikes <dir with result.json and images/> \
      --work <scratch dir> --output benchmarks/optimised-model-parity.json

Only the image tower would run on a phone: the prompts are fixed, so the server computes
their text embeddings once (here, with each model's own pinned text tower). Each photo's
windows are pre-processed once per model, then every artefact (exported, quantised,
lower-precision or smaller) encodes them in its own process. Candidates are scored
against the same text embeddings and compared with the reference by
weedz.discovery.parity. Artefacts and pixels are written under --work, never to the pilot.
"""

import argparse
import copy
import json
import platform
import subprocess
import sys
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any, cast

import numpy as np

from weedz.discovery.parity import THRESHOLDS, compare, encoding_cost

ENCODER = Path(__file__).with_name("encode_variant.py")
PROVENANCE = ["model", "model_key", "revision", "weights_sha256"]
REFERENCE = {"model": "bioclip-2", "artefact": "fp32"}
# Artefact -> how it runs and its file name under --work/<model>/.
ARTEFACTS = {
    "fp32": ("torch", "visual-fp32.pt"),
    "fp16": ("torch", "visual-fp16.pt"),
    "onnx": ("onnx", "visual.onnx"),
    "int8": ("onnx", "visual-int8.onnx"),
    "int8-per-channel": ("onnx", "visual-int8-per-channel.onnx"),
}
VARIANTS: dict[str, dict[str, str]] = {
    "onnx-fp32": {
        "model": "bioclip-2",
        "artefact": "onnx",
        "description": "BioCLIP 2 image tower exported to ONNX, fp32 (export error only)",
    },
    "onnx-int8": {
        "model": "bioclip-2",
        "artefact": "int8",
        "description": "ONNX image tower, dynamic int8 weights (onnxruntime, per tensor)",
    },
    "onnx-int8-per-channel": {
        "model": "bioclip-2",
        "artefact": "int8-per-channel",
        "description": "ONNX image tower, dynamic int8 weights (onnxruntime, per channel)",
    },
    "torch-fp16": {
        "model": "bioclip-2",
        "artefact": "fp16",
        "description": "BioCLIP 2 image tower with fp16 weights and fp16 compute",
    },
    "bioclip-vit-b16": {
        "model": "bioclip",
        "artefact": "fp32",
        "description": "Smaller tower: original BioCLIP ViT-B/16, fp32, with its own text",
    },
    "bioclip-vit-b16-onnx-int8": {
        "model": "bioclip",
        "artefact": "int8",
        "description": "Original BioCLIP ViT-B/16 image tower, ONNX, dynamic int8 weights",
    },
}
METHOD = (
    "The 30 pilot photos (with their original-subject comparison, as in a run) and 39 "
    "source-labelled lookalike photos (no subject prompt, as in #11) are cut into ranking "
    "revision 4 windows. Each pinned model's text tower embeds the fixed prompts once, as "
    "a server would for a device. Each image-tower artefact encodes every window in its "
    "own process on CPU with 4 threads and batches of up to 16, the first photo warmed up "
    "untimed. A candidate's window similarities are read like a run's and compared with "
    "the BioCLIP 2 fp32 reference against versioned thresholds. Size is the artefact on "
    "disk; peak memory is the encoding process's peak resident set; latency is image "
    "encoding only (pre-processing excluded)."
)
CAVEATS = (
    "Desktop CPU latency and memory are not phone latency or memory: phones differ in CPU, "
    "accelerators, runtime and thermal limits, and platform conversion (Core ML, TFLite, "
    "ExecuTorch) is deferred to the platform choice (#50). Parity means agreement with the "
    "reference on 69 source-labelled photos, not accuracy; the pilot has no independent "
    "background-plant labels (#12). A variant that keeps parity here can still diverge on "
    "photos unlike these."
)
COMMAND = (
    "uv run python scripts/compare_optimised.py --pilot-dir <scratch copy of data/pilot> "
    "--run nelson-tasman-3e62ad801459 --lookalikes <lookalike dir> --work <scratch dir> "
    "--output benchmarks/optimised-model-parity.json"
)


def encode_in_process(
    kind: str, artefact: Path, pixels: Path, ids: list[str], out: Path
) -> dict[str, Any]:
    """Run encode_variant.py in a fresh interpreter; return its timings and memory."""
    id_file = out.with_suffix(".ids.json")
    id_file.write_text(json.dumps(ids))
    command = [sys.executable, str(ENCODER), "--kind", kind, "--artefact", str(artefact)]
    command += ["--pixels", str(pixels), "--ids", str(id_file), "--out", str(out)]
    finished = subprocess.run(command, check=True, capture_output=True, text=True)
    return json.loads(finished.stdout.strip().splitlines()[-1])


def results(
    embeddings: Mapping[str, np.ndarray],
    texts: Mapping[str, np.ndarray],
    layout: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Screening results as a run stores them: normalised windows against each photo's text."""
    found = {}
    for pid, features in embeddings.items():
        unit = features / np.linalg.norm(features, axis=1, keepdims=True)
        found[pid] = dict(layout[pid]) | {"window_similarities": (unit @ texts[pid].T).tolist()}
    return found


def conclusion(variants: Mapping[str, Mapping[str, Any]]) -> str:
    kept = [name for name, item in variants.items() if item["parity"]["passed"]]
    failed = [name for name in variants if name not in kept]
    return (
        f"Kept parity: {', '.join(kept) or 'none'}. Failed parity: {', '.join(failed) or 'none'}. "
        f"Measured against thresholds version {THRESHOLDS['version']}."
    )


def document(
    variants: Mapping[str, Mapping[str, Any]],
    reference_metadata: Mapping[str, Any],
    reference_cost: Mapping[str, Any],
    inputs: Mapping[str, Any],
    machine: Mapping[str, Any],
    assessed: str,
) -> dict[str, Any]:
    """The benchmark file exactly as committed; thresholds once, not per variant."""
    trimmed = {
        name: dict(item)
        | {"parity": {k: v for k, v in item["parity"].items() if k != "thresholds"}}
        for name, item in variants.items()
    }
    return {
        "schema": 1,
        "assessed": assessed,
        "issue": "https://github.com/gardner/weedz/issues/52",
        "related": ["https://github.com/gardner/weedz/issues/51"],
        "method": METHOD,
        "caveats": CAVEATS,
        "command": COMMAND,
        "machine": dict(machine),
        "inputs": dict(inputs),
        "thresholds": THRESHOLDS,
        "conclusion": conclusion(variants),
        "reference": {
            "model": {name: reference_metadata[name] for name in PROVENANCE},
            "artefact": "image tower, PyTorch fp32 (what runs use)",
            "cost": dict(reference_cost),
        },
        "variants": trimmed,
    }


def collect_photos(args: argparse.Namespace) -> list[dict[str, Any]]:
    """Pilot and lookalike photos, each with its image path and subject prompt label."""
    from weedz.discovery.inference import subject_label
    from weedz.discovery.lookalikes import lookalike_photos
    from weedz.discovery.store import Store

    store = Store(args.pilot_dir)
    pilot = [
        photo | {"path": store.root / photo["image_path"], "subject": subject_label(photo)}
        for photo in store.photos(args.run)
    ]
    items = json.loads((args.lookalikes / "result.json").read_text())["photos"]
    looks = [
        photo | {"path": args.lookalikes / photo["image"], "subject": None}
        for photo in lookalike_photos(items)
    ]
    return pilot + looks


def open_image(path: Path) -> Any:
    from PIL import Image, ImageOps

    with Image.open(path) as original:
        return ImageOps.exif_transpose(original).convert("RGB")


def window_layout(photos: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Model-independent geometry: image size and featureless tiles, as Screener.screen."""
    from weedz.discovery.inference import featureless, region_boxes

    layout = {}
    for photo in photos:
        image = open_image(photo["path"])
        boxes = region_boxes(*image.size)
        excluded = [i for i, box in enumerate(boxes) if i and featureless(image.crop(box))]
        layout[photo["id"]] = {
            "width": image.width,
            "height": image.height,
            "featureless_windows": excluded,
        }
    return layout


def export_artefacts(visual: Any, folder: Path, needed: set[str]) -> None:
    """Write each needed image-tower artefact once; existing files are reused."""
    import torch
    from onnxruntime.quantization import QuantType, quantize_dynamic

    paths = {name: folder / file for name, (_, file) in ARTEFACTS.items()}
    if "fp32" in needed and not paths["fp32"].exists():
        torch.save(visual, paths["fp32"])
    if "fp16" in needed and not paths["fp16"].exists():
        torch.save(copy.deepcopy(visual).half(), paths["fp16"])
    if needed & {"onnx", "int8", "int8-per-channel"} and not paths["onnx"].exists():
        # The TorchScript exporter needs no extra dependency and handles open_clip's ViT.
        torch.onnx.export(
            visual,
            (torch.zeros(1, 3, 224, 224),),
            str(paths["onnx"]),
            input_names=["pixels"],
            output_names=["embedding"],
            dynamic_axes={"pixels": {0: "batch"}, "embedding": {0: "batch"}},
            dynamo=False,
            opset_version=17,
        )
    for name, per_channel in [("int8", False), ("int8-per-channel", True)]:
        if name in needed and not paths[name].exists():
            quantize_dynamic(
                paths["onnx"], paths[name], weight_type=QuantType.QInt8, per_channel=per_channel
            )


def prepare(key: str, photos: list[dict[str, Any]], work: Path, needed: set[str]) -> dict[str, Any]:
    """One model's text embeddings, pre-processed windows and artefacts."""
    import torch

    from weedz.discovery.inference import Screener, prompt, region_boxes, square_view

    screener = Screener.load(model=key)
    folder = work / key
    pixels = folder / "pixels"
    pixels.mkdir(parents=True, exist_ok=True)
    texts = {}
    for photo in photos:
        image = open_image(photo["path"])
        views = [square_view(image, box) for box in region_boxes(*image.size)]
        batch = torch.stack([screener.transform(view) for view in views]).numpy()
        np.save(pixels / f"{photo['id']}.npy", batch.astype(np.float32))
        text = screener.text
        if photo["subject"]:
            text = torch.cat([text, screener.encode_text([prompt(photo["subject"])])])
        texts[photo["id"]] = text.float().numpy()
    export_artefacts(cast(Any, screener.model).visual, folder, needed)
    return {"metadata": screener.metadata, "texts": texts, "pixels": pixels, "folder": folder}


def measure(model: Mapping[str, Any], artefact: str, ids: list[str], layout: dict) -> tuple:
    """Encode every photo with one artefact; its screening results and cost."""
    kind, file = ARTEFACTS[artefact]
    path = model["folder"] / file
    out = model["folder"] / f"embeddings-{artefact}.npz"
    stats = encode_in_process(kind, path, model["pixels"], ids, out)
    with np.load(out) as stored:
        embeddings = {pid: stored[pid] for pid in ids}
    windows = [len(embeddings[pid]) for pid in ids]
    size = sum(f.stat().st_size for f in path.parent.glob(f"{path.name}*"))  # external data
    cost = encoding_cost(
        size, stats["peak_rss_bytes"], stats["baseline_rss_bytes"], stats["seconds"], windows
    )
    return results(embeddings, model["texts"], layout), cost


def machine() -> dict[str, Any]:
    import onnxruntime
    import torch

    cpuinfo = Path("/proc/cpuinfo")
    lines = cpuinfo.read_text().splitlines() if cpuinfo.exists() else []
    names = [line.split(":", 1)[1].strip() for line in lines if line.startswith("model name")]
    return {
        "cpu": names[0] if names else platform.processor(),
        "threads": 4,
        "os": platform.platform(),
        "torch": torch.__version__,
        "onnxruntime": onnxruntime.__version__,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    photos = collect_photos(args)
    ids = [photo["id"] for photo in photos]
    layout = window_layout(photos)
    chosen = {name: VARIANTS[name] for name in args.variants}
    needed: dict[str, set[str]] = {REFERENCE["model"]: {REFERENCE["artefact"]}}
    for item in chosen.values():
        needed.setdefault(item["model"], set()).add(item["artefact"])
    models = {key: prepare(key, photos, args.work, wanted) for key, wanted in needed.items()}
    reference, reference_cost = measure(
        models[REFERENCE["model"]], REFERENCE["artefact"], ids, layout
    )
    variants = {}
    for name, item in chosen.items():
        candidate, cost = measure(models[item["model"]], item["artefact"], ids, layout)
        model = models[item["model"]]["metadata"]
        variants[name] = {
            "model": model["model"],
            "revision": model["revision"],
            "description": item["description"],
            "cost": cost,
            "parity": compare(reference, candidate, photos),
        }
        print(name, json.dumps(variants[name]["parity"]["checks"]), json.dumps(cost))
    inputs = {
        "run": args.run,
        "pilot_photos": sum(photo["cohort"] != "lookalike" for photo in photos),
        "lookalike_photos": sum(photo["cohort"] == "lookalike" for photo in photos),
    }
    metadata = models[REFERENCE["model"]]["metadata"]
    today = date.today().isoformat()
    return document(variants, metadata, reference_cost, inputs, machine(), today)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compare optimised image towers for parity")
    parser.add_argument("--pilot-dir", type=Path, required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--lookalikes", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--variants", nargs="+", default=list(VARIANTS), choices=list(VARIANTS))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = run(args)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
