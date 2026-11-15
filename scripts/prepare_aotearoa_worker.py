"""Preflight the CPU NZ variant and an explicitly pinned, previously completed SAM2 artifact."""

import argparse
import hashlib
import json
from pathlib import Path

from weedz.batches.aotearoa_runtime import prepare_aotearoa_config
from weedz.batches.receipts import write_receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--proposals", required=True, help="Relative artifact path under root")
    parser.add_argument("--proposals-sha256", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    config = prepare_aotearoa_config(
        root,
        args.checkpoint,
        args.labels,
        {"path": args.proposals, "sha256": args.proposals_sha256},
    )
    digest = hashlib.sha256(
        json.dumps(config, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()
    receipt = write_receipt(root, f"worker-configs/{digest}.json", config)
    print(json.dumps(receipt), flush=True)


if __name__ == "__main__":
    main()
