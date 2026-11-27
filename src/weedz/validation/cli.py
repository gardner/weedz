"""List and run validation checks, then build the scorecard from their results."""

import argparse
import json
import logging
import time
from pathlib import Path

from weedz.validation.compare import compare_scorecards
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
    compare = actions.add_parser("compare", help="Compare a baseline scorecard with rerun results")
    compare.add_argument("baseline", type=Path)
    compare.add_argument("results", nargs="+", type=Path)
    compare.add_argument("--markdown", type=Path)
    return command


def _run(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
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
    # Skip the previous scorecard, which a `benchmarks/validation/*.json` glob includes.
    paths = [path for path in args.results if path.resolve() != args.output.resolve()]
    results = [CheckResult.model_validate_json(path.read_text()) for path in paths]
    card = Scorecard.collect(results)
    card.write(args.output)
    if args.markdown:
        args.markdown.write_text(card.markdown())


def _rerun(paths: list[Path], baseline: Path) -> Scorecard:
    """Collect reruns; a check's own result file wins over a scorecard that also holds it.

    The documented `benchmarks/validation/*.json` glob includes the baseline scorecard
    itself. It is skipped (unless it is the only input), so a check that wasn't rerun
    shows as removed instead of being silently filled in from the baseline.
    """
    others = [path for path in paths if path.resolve() != baseline.resolve()]
    paths = others or paths
    single: dict[str, CheckResult] = {}
    carded: dict[str, CheckResult] = {}
    for path in paths:
        data = json.loads(path.read_text())
        if "results" in data:
            carded |= {result.check: result for result in Scorecard.model_validate(data).results}
        else:
            result = CheckResult.model_validate(data)
            if result.check in single:
                raise ValueError(f"Two result files for {result.check}; pass one per check")
            single[result.check] = result
    return Scorecard.collect(list((carded | single).values()))


def _compare(args: argparse.Namespace) -> None:
    comparison = compare_scorecards(
        Scorecard.read(args.baseline), _rerun(args.results, args.baseline)
    )
    print(comparison.markdown(limit=20), end="")
    if args.markdown:
        args.markdown.write_text(comparison.markdown())
    if comparison.exit_code:
        raise SystemExit(comparison.exit_code)


def main(argv: list[str]) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parser().parse_args(argv)
    if args.action in {"list", "run"}:
        import weedz.validation.checks  # noqa: F401  (registers the built-in checks)

    if args.action == "list":
        for check in sorted(REGISTRY.values(), key=lambda check: (check.stage, check.name)):
            print(f"{check.stage:16} {check.name:32} {check.dataset}")
    elif args.action == "run":
        _run(args)
    elif args.action == "compare":
        _compare(args)
    else:
        _scorecard(args)
