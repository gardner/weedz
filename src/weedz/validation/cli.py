"""List and run validation checks, then build the scorecard from their results."""

import argparse
import logging
import time
from pathlib import Path

from weedz.validation.registry import REGISTRY, RunContext
from weedz.validation.scorecard import CheckResult, Scorecard

logger = logging.getLogger(__name__)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="validate", description=__doc__)
    actions = command.add_subparsers(dest="action", required=True)
    actions.add_parser("list", help="Show the registered checks")
    run = actions.add_parser("run", help="Run one check and save its result")
    run.add_argument("check")
    run.add_argument("--data-root", type=Path, required=True)
    run.add_argument("--cache-dir", type=Path)
    run.add_argument("--device", default="cpu")
    run.add_argument("--limit", type=int, help="Score only the first N items (smoke runs)")
    run.add_argument("--output", type=Path, required=True, help="Directory for <check>.json")
    card = actions.add_parser("scorecard", help="Collect check results into one scorecard")
    card.add_argument("results", nargs="+", type=Path)
    card.add_argument("--output", type=Path, required=True)
    card.add_argument("--markdown", type=Path)
    return command


def _run(args: argparse.Namespace) -> None:
    check = REGISTRY[args.check]
    context = RunContext(
        data_root=args.data_root,
        cache_dir=args.cache_dir or args.data_root / ".cache",
        device=args.device,
        limit=args.limit,
    )
    started = time.monotonic()
    result = check.run(context)
    if result.seconds is None:
        result = result.model_copy(update={"seconds": round(time.monotonic() - started, 2)})
    args.output.mkdir(parents=True, exist_ok=True)
    path = args.output / f"{check.name}.json"
    path.write_text(result.model_dump_json(indent=2) + "\n")
    logger.info("Saved %s", path)


def _scorecard(args: argparse.Namespace) -> None:
    results = [CheckResult.model_validate_json(path.read_text()) for path in args.results]
    card = Scorecard.collect(results)
    card.write(args.output)
    if args.markdown:
        args.markdown.write_text(card.markdown())


def main(argv: list[str]) -> None:
    import weedz.validation.checks  # noqa: F401  (registers the built-in checks)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parser().parse_args(argv)
    if args.action == "list":
        for check in sorted(REGISTRY.values(), key=lambda check: (check.stage, check.name)):
            print(f"{check.stage:16} {check.name:32} {check.dataset}")
    elif args.action == "run":
        _run(args)
    else:
        _scorecard(args)
