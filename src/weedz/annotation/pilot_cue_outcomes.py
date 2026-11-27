"""Summarize independent review of frozen supplemental camera cues."""

import argparse
import json
from pathlib import Path

from weedz.annotation.pilot_effort import Row, _load, _package, summarize
from weedz.annotation.pilot_outcomes import evaluate_blind


def report_cues(package: Path, export: Path, cue_receipt: Path) -> Row:
    tasks, package_sha = _package(package)
    _, task_sha = _load(package / "tasks.json")
    receipt, receipt_sha = _load(cue_receipt)
    if (receipt.get("package_manifest_sha256"), receipt.get("task_file_sha256")) != (
        package_sha,
        task_sha,
    ):
        raise ValueError("Package does not match the cue receipt")
    if any(not {"review_hint", "search_preview"} <= task["data"].keys() for task in tasks):
        raise ValueError("Expected a supplemental assisted package")
    decisions = receipt["decisions"]
    if any(row.get("target") is None for row in decisions):
        raise ValueError("Every supplemental task needs its original cue taxon")
    exported, export_sha = _load(export)
    outcomes = evaluate_blind(tasks, exported, decisions)
    return {
        "effort": summarize(tasks, exported),
        "cue_outcomes": {
            key: outcomes[key]
            for key in (
                "consensus",
                "suggestions_supported",
                "suggestions_unsupported",
                "suggestions_unassessed",
            )
        },
        "inputs": {
            "package_manifest_sha256": package_sha,
            "cue_receipt_sha256": receipt_sha,
            "export_sha256": export_sha,
        },
        "interpretation": (
            "Cue support requires agreement between at least two reviewer accounts. "
            "These selected cases cannot estimate population precision or recall."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--export", required=True, type=Path)
    parser.add_argument("--cue-receipt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = report_cues(args.package, args.export, args.cue_receipt)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
