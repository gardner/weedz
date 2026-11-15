"""Run the pinned NZ full-frame baseline; retain all logits without creating human labels."""

import argparse
import hashlib
import io
import json
import time
from pathlib import Path

import numpy as np

from weedz.classification.aotearoa import AotearoaClassifier
from weedz.classification.batch import classify_batch
from weedz.manifest import write_atomic


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--media-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a new output directory; completed evidence is never overwritten")
    started = time.monotonic()
    model = AotearoaClassifier.load(args.checkpoint, args.labels)
    loaded = time.monotonic()
    logits: list[np.ndarray] = []
    model.on_logits = logits.append
    args.output.mkdir(parents=True)
    result = classify_batch(args.manifest, args.media_root, args.output / "predictions.json", model)
    buffer = io.BytesIO()
    np.savez_compressed(
        buffer,
        logits=np.stack(logits),
        external_ids=np.asarray([row["external_id"] for row in result["predictions"]]),
        labels=np.asarray(model.labels),
    )
    encoded = buffer.getvalue()
    write_atomic(args.output / "full-logits.npz", encoded)
    receipt = {
        "schema": 1,
        "model_version": result["model_version"],
        "manifest_sha256": result["manifest_sha256"],
        "result_sha256": result["result_sha256"],
        "logits_sha256": hashlib.sha256(encoded).hexdigest(),
        "completed": len(result["predictions"]),
        "classes": len(model.labels),
        "load_seconds": loaded - started,
        "inference_and_output_seconds": time.monotonic() - loaded,
        "elapsed_seconds": time.monotonic() - started,
        "provider": model.session.get_providers(),
        "source_policy": "released full-frame416/384; no masks; no human annotation writes",
        "score_policy": "all-class raw-logit softmax, not calibrated identification confidence",
    }
    write_atomic(args.output / "receipt.json", (json.dumps(receipt, indent=2) + "\n").encode())
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
