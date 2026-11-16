"""Generate opt-in review XML or import a pinned completed-human export offline."""

import argparse
from pathlib import Path

from demo_paths import new_output

from weedz.annotation.gold_config import gold_config
from weedz.annotation.import_pipeline import ImportInputs, import_reviews
from weedz.rights_profiles import PROFILES, PUBLIC_PROFILE


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    config = commands.add_parser("config", help="Write a new opt-in review configuration")
    imported = commands.add_parser(
        "import", help="Import completed human reviews; no service calls"
    )
    for sub in (config, imported):
        sub.add_argument("--taxon", action="append", default=[])
        sub.add_argument("--category", action="append", default=[])
        sub.add_argument("--output", required=True, type=Path)
    for name in ("package", "export", "config"):
        imported.add_argument(f"--{name}", required=True, type=Path)
        imported.add_argument(f"--{name}-sha256", required=True)
    imported.add_argument("--project", required=True, help="Stable source project namespace")
    imported.add_argument("--project-id", required=True, type=int)
    imported.add_argument("--rights-profile", choices=tuple(PROFILES), default=PUBLIC_PROFILE)
    imported.add_argument("--previous", type=Path)
    imported.add_argument("--previous-sha256")
    return root


def main() -> None:
    cli = parser()
    args = cli.parse_args()
    taxa, categories = tuple(args.taxon), tuple(args.category)
    try:
        if args.command == "config":
            raw = gold_config(taxa, categories).encode("utf-8")
            output = new_output(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb") as stream:
                stream.write(raw)
        else:
            request = ImportInputs(
                args.package,
                args.package_sha256,
                args.export,
                args.export_sha256,
                args.config,
                args.config_sha256,
                args.project,
                args.project_id,
                taxa,
                categories,
                args.rights_profile,
            )
            receipt = import_reviews(
                request, args.output, previous=args.previous, previous_sha256=args.previous_sha256
            )
            print(
                f"Imported {receipt['imported_revisions']} new human revisions into {args.output}"
            )
    except (OSError, ValueError, KeyError, TypeError) as error:
        cli.exit(1, f"Review import refused: {error}\n")


if __name__ == "__main__":
    main()
