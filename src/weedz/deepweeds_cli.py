"""Explicit local-only DeepWeeds conversion; downloads and inference are separate."""

import argparse
import json
import zipfile
from pathlib import Path

from weedz.deepweeds import materialize


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Convert pinned cached DeepWeeds into credited batches"
    )
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, required=True, help="Explicit 1–17509 image budget")
    parser.add_argument(
        "--batch-size", type=int, default=100, help="1–1000 images per closed batch"
    )
    args = parser.parse_args(argv)
    try:
        result = materialize(
            args.archive, args.labels, args.output, limit=args.limit, batch_size=args.batch_size
        )
    except (OSError, ValueError, SyntaxError, zipfile.BadZipFile) as error:
        parser.exit(1, f"deepweeds-batches: {error}\n")
    print(json.dumps(result))
