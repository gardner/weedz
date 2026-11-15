"""Capture the pinned CPU classifier identity and reuse an existing SAM profile."""

import argparse
import hashlib
import json
from pathlib import Path

from weedz.batches.receipts import write_receipt
from weedz.batches.weedscan_runtime import prepare_weedscan_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--proposals", required=True, help="Relative artifact path inside the root")
    parser.add_argument("--proposals-sha256", required=True)
    args = parser.parse_args()
    config = prepare_weedscan_config(
        args.root,
        args.checkpoint,
        args.labels,
        {"path": args.proposals, "sha256": args.proposals_sha256},
    )
    stamp = hashlib.sha256(json.dumps(config, sort_keys=True, allow_nan=False).encode()).hexdigest()
    print(json.dumps(write_receipt(args.root.resolve(), f"worker-configs/{stamp}.json", config)))


if __name__ == "__main__":
    main()
