"""Run a resident pretrained classifier over closed, hash-verified canonical batches."""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from weedz.classification.batch import Profile, classify_batch
from weedz.classification.plantclef import PlantClassifier
from weedz.manifest import write_atomic


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--profile", choices=["frame", "tiles"], default="frame")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batches", type=int, required=True)
    parser.add_argument("--wait", action="store_true", help="Wait for each ready.json marker")
    args = parser.parse_args()
    if not 1 <= args.batches <= 10_000:
        parser.error("Choose between 1 and 10,000 closed batches")
    profile: Profile = "frame" if args.profile == "frame" else "tiles"
    root = args.root.resolve()
    if not root.is_dir():
        parser.error("The materialized batch root must already exist")
    model = PlantClassifier.load(args.checkpoint, args.labels, args.device)
    started, completed = time.monotonic(), 0
    for index in range(1, args.batches + 1):
        directory = (root / f"batch-{index:04d}").resolve()
        if not directory.is_relative_to(root):
            raise ValueError("Batch directory escapes the declared root")
        while not (directory / "ready.json").exists():
            if not args.wait:
                raise ValueError(f"Batch {index} has not been closed by its producer")
            time.sleep(2)
        result = classify_batch(
            directory / "samples.jsonl",
            directory,
            directory / f"plantclef-{profile}.json",
            model,
            profile,
        )
        completed += len(result["predictions"])
        progress = {
            "pid": os.getpid(),
            "device": args.device,
            "profile": profile,
            "completed": completed,
            "batches": index,
            "expected_batches": args.batches,
            "updated_at": datetime.now(UTC).isoformat(),
            "elapsed_seconds": round(time.monotonic() - started, 2),
        }
        write_atomic(
            root / f"plantclef-{profile}-progress.json",
            (json.dumps(progress, indent=2) + "\n").encode(),
        )
        print(json.dumps(progress), flush=True)


if __name__ == "__main__":
    main()
