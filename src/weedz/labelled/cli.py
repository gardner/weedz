"""Local source conversion and bounded review preparation, never model inference or LS writes."""

import argparse
import json
import tarfile
import zipfile
from pathlib import Path

from weedz.labelled import cwfid, imageweeds, nz_review
from weedz.labelled.images import FORMATS


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="source", required=True)
    for name in ("cwfid", "imageweeds"):
        command = commands.add_parser(name)
        command.add_argument("--archive", type=Path, required=True)
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--limit", type=int, required=True)
        if name == "imageweeds":
            command.add_argument("--crop", choices=tuple(imageweeds.PROFILES), required=True)
            command.add_argument("--format", choices=FORMATS, default="lossless-rgb-png")
    command = commands.add_parser("nz-review")
    command.add_argument(
        "--prior-root",
        type=Path,
        required=True,
        help="Read-only previously exposed pilot metadata/images",
    )
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--per-stratum", type=int, default=20)
    args = parser.parse_args(argv)
    try:
        sha = _prepare(args)
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        parser.exit(1, f"labelled-batches: {error}\n")
    print(json.dumps({"output": str(args.output.resolve()), "manifest_sha256": sha}))


def _prepare(args: argparse.Namespace) -> str:
    if args.source == "cwfid":
        return cwfid.prepare(args.archive, args.output, limit=args.limit)
    if args.source == "imageweeds":
        return imageweeds.prepare(
            args.archive, args.output, crop=args.crop, limit=args.limit, image_format=args.format
        )
    return nz_review.prepare(args.prior_root, args.output, per_stratum=args.per_stratum)
