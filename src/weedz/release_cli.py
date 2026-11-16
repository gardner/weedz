"""`uv run main.py release ...`: build, verify and advance frozen dataset releases."""

import argparse
import json
from pathlib import Path

from weedz.baseline_release import write_leafy_spurge_release
from weedz.manifest import read_manifest
from weedz.release import (
    STATUS_ORDER,
    Release,
    ReleaseSpec,
    read_release,
    record_test_status,
    write_release,
)
from weedz.review_snapshot import write_review_snapshot


def _summary(release: Release, directory: Path) -> str:
    sizes = " · ".join(
        f"{name} {len(release.splits[name].samples)}" for name in ("fit", "validation", "test")
    )
    return (
        f"Release {release.id}: {sizes} · excluded {len(release.excluded)}; "
        f"test {release.test_status}\n{directory.resolve()}"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="weedz release", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser(
        "freeze", help="Freeze a pinned reviewed manifest with an explicit release spec"
    )
    freeze.add_argument("--manifest", type=Path, required=True)
    freeze.add_argument("--manifest-sha256", required=True)
    freeze.add_argument("--spec", type=Path, required=True)
    freeze.add_argument("--assets-root", type=Path)
    freeze.add_argument("--output-dir", type=Path, required=True)
    snapshot = commands.add_parser(
        "review-snapshot", help="Export an existing review store read-only"
    )
    snapshot.add_argument("--source", type=Path, required=True)
    snapshot.add_argument("--run", required=True)
    snapshot.add_argument("--namespace", required=True)
    snapshot.add_argument("--output-dir", type=Path, required=True)
    leafy = commands.add_parser(
        "leafy-spurge", help="Freeze the baseline split from verified local data (no download)"
    )
    leafy.add_argument("--data-dir", type=Path, default=Path("data/leafy-spurge"))
    leafy.add_argument("--output-dir", type=Path, required=True, help="New or empty directory")
    leafy.add_argument(
        "--check-run", type=Path, help="A run.json whose partition IDs the release must match"
    )
    status = commands.add_parser("status", help="Append a test status change")
    status.add_argument("directory", type=Path)
    status.add_argument("status", choices=STATUS_ORDER)
    status.add_argument("--note", required=True, help="Why the status changed")
    verify = commands.add_parser("verify", help="Check a release's record and manifest")
    verify.add_argument("directory", type=Path)
    return parser


def _run(args: argparse.Namespace) -> str:
    if args.command == "review-snapshot":
        receipt = write_review_snapshot(
            args.source, args.run, args.output_dir, namespace=args.namespace
        )
        return f"Review snapshot: {receipt['count']} samples\n{args.output_dir.resolve()}"
    if args.command == "freeze":
        samples = read_manifest(args.manifest, args.manifest_sha256)
        spec = ReleaseSpec.model_validate_json(args.spec.read_bytes())
        release = write_release(args.output_dir, samples, spec, assets_root=args.assets_root)
        return _summary(release, args.output_dir)
    if args.command == "leafy-spurge":
        expected = None
        if args.check_run:
            expected = json.loads(args.check_run.read_text(encoding="utf-8"))["partitions"]
        release = write_leafy_spurge_release(args.data_dir, args.output_dir, expected=expected)
        matched = f"Partitions match the recorded run {args.check_run}\n" if args.check_run else ""
        return matched + _summary(release, args.output_dir)
    if args.command == "status":
        release = record_test_status(args.directory, args.status, note=args.note)
        return _summary(release, args.directory)
    release, _ = read_release(args.directory)
    return _summary(release, args.directory)


def main(argv: list[str]) -> None:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        print(_run(args))
    except (OSError, KeyError, ValueError) as error:
        parser.exit(1, f"weedz: {error}\n")
