"""Run with `uv run main.py`; use --offline after the first download."""

import argparse
import importlib
import logging
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

from weedz.pipeline import run_pipeline
from weedz.provenance import fetch_dataset, verify_dataset

logger = logging.getLogger("weedz")


def _recall(value: str) -> float:
    target = float(value)
    if not math.isfinite(target) or not 0 < target <= 1:
        raise argparse.ArgumentTypeError("Recall must be greater than zero and at most one")
    return target


# Commands with their own parser: the module whose main() takes the arguments, and whether
# those include the command's own name. Imported only when used, as they are heavy.
TOOLS = {
    name: ("weedz.discovery.cli", True)
    for name in (
        "dev",
        "discover",
        "references",
        "outcomes",
        "package",
        "reference",
        "study",
        "suitability",
    )
} | {
    "reviewers": ("weedz.discovery.access_cli", False),
    "bundles": ("weedz.bundles.cli", False),
    "intake": ("weedz.intake.cli", False),
    "release": ("weedz.release_cli", False),
}


def run_tool(argv: list[str]) -> bool:
    """Hand a tool command to its own parser; False when argv names none."""
    if not argv or argv[0] not in TOOLS:
        return False
    module, with_name = TOOLS[argv[0]]
    importlib.import_module(module).main(argv if with_name else argv[1:])
    return True


def main() -> None:
    if run_tool(sys.argv[1:]):
        return
    parser = argparse.ArgumentParser(description="Leafy Spurge baseline and offline review map")
    parser.add_argument("command", nargs="?", choices=("fetch", "run"), default="run")
    parser.add_argument("--data-dir", type=Path, default=Path("data/leafy-spurge"))
    parser.add_argument(
        "--output-dir", type=Path, help="New or empty directory for this experiment"
    )
    parser.add_argument(
        "--offline", action="store_true", help="Use and verify already downloaded data"
    )
    parser.add_argument(
        "--target-recall", type=_recall, default=0.9, help="Validation recall target"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        if not args.offline:
            logger.info(
                "Preparing the pinned crop dataset (900 images; downloads resume automatically)."
            )
            fetch_dataset(args.data_dir)
        elif args.command == "fetch":
            verify_dataset(args.data_dir)
        if args.command == "fetch":
            logger.info("Dataset ready: %s", args.data_dir.resolve())
            return
        output = args.output_dir or Path("runs") / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        logger.info(
            "Training on survey groups, choosing a validation threshold, then evaluating test."
        )
        metrics = run_pipeline(args.data_dir, output, target_recall=args.target_recall)
    except (OSError, ValueError) as error:
        parser.exit(1, f"weedz: {error}\n")
    logger.info(
        "Test: recall %.3f · precision %.3f · accuracy %.3f",
        metrics["test"]["recall"],
        metrics["test"]["precision"],
        metrics["test"]["accuracy"],
    )
    logger.info("Review map: %s", (output / "map.html").resolve())


if __name__ == "__main__":
    main()
