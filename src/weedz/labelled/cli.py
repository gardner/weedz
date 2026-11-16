"""Local source conversion and bounded review preparation, never model inference or LS writes."""

import argparse
import json
import tarfile
import zipfile
from pathlib import Path

from weedz.labelled import cwfid, imageweeds, nz_review
from weedz.labelled.audit import audit
from weedz.labelled.images import FORMATS
from weedz.labelled.publication import digest, json_bytes, output_namespace, publish


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
            command.add_argument(
                "--prepared-images",
                type=Path,
                help="Optional existing RGB PNG cache, verified against source pixels",
            )
    command = commands.add_parser("nz-review")
    command.add_argument(
        "--prior-root",
        type=Path,
        required=True,
        help="Read-only previously exposed pilot metadata/images",
    )
    command.add_argument("--output", type=Path, required=True)
    command.add_argument("--per-stratum", type=int, default=20)
    command.add_argument(
        "--prior-evidence",
        type=Path,
        action="append",
        default=[],
        help="Prior local canonical JSONL or source provenance JSON; repeatable",
    )
    command = commands.add_parser("audit")
    command.add_argument("--manifest", type=Path, action="append", required=True)
    command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        sha = _prepare(args)
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
        parser.exit(1, f"labelled-batches: {error}\n")
    key = "report_sha256" if args.source == "audit" else "manifest_sha256"
    print(json.dumps({"output": str(args.output.resolve()), key: sha}))


def _prepare(args: argparse.Namespace) -> str:
    if args.source == "audit":
        output = args.output
        for manifest in args.manifest:
            output = output_namespace(output, manifest.parent)
        raw = json_bytes(audit(tuple(args.manifest)))
        publish(output, raw)
        return digest(raw)
    if args.source == "cwfid":
        return cwfid.prepare(args.archive, args.output, limit=args.limit)
    if args.source == "imageweeds":
        return imageweeds.prepare(
            args.archive,
            args.output,
            crop=args.crop,
            limit=args.limit,
            image_format=args.format,
            prepared_images=args.prepared_images,
        )
    return nz_review.prepare(
        args.prior_root,
        args.output,
        per_stratum=args.per_stratum,
        prior_evidence=tuple(args.prior_evidence),
    )
