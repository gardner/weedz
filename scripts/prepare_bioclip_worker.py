"""Preflight a resident GPU BioCLIP model and register cached-only SAM batch profiles."""

import argparse
import hashlib
import json
from pathlib import Path

from weedz.batches.bioclip_runtime import prepare_bioclip_config
from weedz.batches.receipts import write_receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--proposals", required=True)
    parser.add_argument("--proposals-sha256", required=True)
    parser.add_argument("--model", choices=["bioclip", "bioclip-2"], default="bioclip-2")
    args = parser.parse_args()
    config = prepare_bioclip_config(
        args.root, {"path": args.proposals, "sha256": args.proposals_sha256}, args.model
    )
    stamp = hashlib.sha256(json.dumps(config, sort_keys=True, allow_nan=False).encode()).hexdigest()
    print(json.dumps(write_receipt(args.root.resolve(), f"worker-configs/{stamp}.json", config)))


if __name__ == "__main__":
    main()
