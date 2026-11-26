"""Measure blind NZ pilot outcomes after joining sealed suggestions to review exports."""

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from weedz.annotation.pilot_effort import (
    Row,
    _bound_task,
    _identity,
    _load,
    _package,
    _positive_id,
    _watchlist_answer,
)
from weedz.discovery.records import SPECIES

Vote = frozenset[str] | None


def _species_choices(results: list[Row]) -> frozenset[str]:
    rows = [result for result in results if result.get("from_name") == "watchlist_species"]
    if not rows:
        return frozenset()
    if len(rows) != 1 or rows[0].get("type") != "choices" or rows[0].get("to_name") != "image":
        raise ValueError("Invalid or duplicate watchlist species control")
    choices = rows[0].get("value", {}).get("choices")
    if not isinstance(choices, list) or any(not isinstance(v, str) for v in choices):
        raise ValueError("Expected watchlist taxa as a list of strings")
    if not set(choices) <= SPECIES.keys() or len(choices) != len(set(choices)):
        raise ValueError("Unknown or duplicate watchlist taxa")
    return frozenset(choices)


def _vote(results: list[Row]) -> Vote:
    answer = _watchlist_answer(results)
    species = _species_choices(results)
    if answer == "Watchlist plant visible":
        return species or None
    if species:
        return None
    return frozenset() if answer == "No watchlist plant visible" else None


def _reviewer(annotation: Row) -> int:
    reviewer = annotation.get("completed_by")
    return _positive_id(reviewer["id"] if isinstance(reviewer, dict) else reviewer)


def _collect(task: Row, seen_annotations: set[int]) -> dict[int, set[Vote]]:
    task_id = _positive_id(task.get("id"))
    by_reviewer: dict[int, set[Vote]] = {}
    for annotation in task["annotations"]:
        identifier = _positive_id(annotation.get("id"))
        if identifier in seen_annotations:
            raise ValueError("Duplicate annotation in pilot export")
        seen_annotations.add(identifier)
        if (
            _positive_id(annotation.get("task")) != task_id
            or type(annotation.get("was_cancelled")) is not bool
        ):
            raise ValueError("Invalid annotation task identity or cancellation status")
        if annotation["was_cancelled"] or annotation.get("ground_truth") is True:
            continue
        by_reviewer.setdefault(_reviewer(annotation), set()).add(_vote(annotation["result"]))
    return by_reviewer


def _consensus(reviews: dict[int, set[Vote]]) -> tuple[str, Vote]:
    if not reviews:
        return "unreviewed", None
    responses = set.union(*reviews.values())
    if None in responses:
        return "uncertain", None
    if len(responses) != 1:
        return "disagreement", None
    if len(reviews) < 2:
        return "single_reviewer", None
    species = next(iter(responses))
    return ("agreed_visible" if species else "agreed_no_visible"), species


def _targets(tasks: dict[str, Row], decisions: list[Row]) -> dict[str, str | None]:
    targets = {}
    for row in decisions:
        key = row.get("external_id")
        if key not in tasks or key in targets:
            raise ValueError("Pilot task identities must match the sealed decisions")
        target = row["target"]
        if row.get("image_sha256") != tasks[key]["meta"]["image_sha256"]:
            raise ValueError("Pilot image hashes must match the sealed decisions")
        if target is not None and (not isinstance(target, str) or target not in SPECIES):
            raise ValueError("A sealed decision must be an exact watchlist species or empty")
        targets[key] = target
    if targets.keys() != tasks.keys():
        raise ValueError("Pilot package coverage must match the sealed decisions")
    return targets


@dataclass
class Outcomes:
    consensus: Counter[str] = field(default_factory=Counter)
    taxa: dict[str, Counter[str]] = field(default_factory=dict)
    counts: Counter[str] = field(default_factory=Counter)

    def add(self, status: str, species: Vote, target: str | None) -> None:
        self.consensus[status] += 1
        if species is None:
            self.counts["suggestions_unassessed"] += target is not None
            return
        self.counts["agreed_visible_taxa"] += len(species)
        self.counts["agreed_taxa_missed"] += len(species) - (target in species)
        for taxon in species:
            self.taxa.setdefault(taxon, Counter()).update(agreed_visible=1, missed=taxon != target)
        if target is not None:
            key = "suggestions_supported" if target in species else "suggestions_unsupported"
            self.counts[key] += 1

    def report(self) -> Row:
        keys = (
            "agreed_visible_taxa",
            "agreed_taxa_missed",
            "suggestions_supported",
            "suggestions_unsupported",
            "suggestions_unassessed",
        )
        return {
            "consensus": dict(sorted(self.consensus.items())),
            "by_visible_taxon": dict(sorted(self.taxa.items())),
            **{key: self.counts[key] for key in keys},
        }


def evaluate_blind(package: list[Row], export: list[Row], decisions: list[Row]) -> Row:
    tasks = {_identity(row): row for row in package}
    if len(tasks) != len(package):
        raise ValueError("Duplicate task identity in the pilot package")
    targets = _targets(tasks, decisions)
    seen_annotations: set[int] = set()
    seen_ids: set[int] = set()
    results: dict[str, dict[int, set[Vote]]] = {}
    for row in export:
        key = _bound_task(row, tasks)
        identifier = _positive_id(row.get("id"))
        if key in results or identifier in seen_ids:
            raise ValueError("Duplicate task in pilot export")
        seen_ids.add(identifier)
        results[key] = _collect(row, seen_annotations)
    outcomes = Outcomes()
    for key, target in targets.items():
        status, species = _consensus(results.get(key, {}))
        outcomes.add(status, species, target)
    return outcomes.report()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind-package", type=Path, required=True)
    parser.add_argument("--blind-export", type=Path, required=True)
    parser.add_argument("--sealed-decisions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    tasks, manifest_sha = _package(args.blind_package, "blind")
    manifest, _ = _load(args.blind_package / "manifest.json")
    seal, seal_sha = _load(args.sealed_decisions)
    if seal.get("package_manifest_sha256") != manifest_sha:
        raise ValueError("Pilot manifest differs from the sealed decisions")
    if seal.get("task_file_sha256") != manifest["files"]["tasks.json"]:
        raise ValueError("Pilot task file differs from the sealed decisions")
    export, export_sha = _load(args.blind_export)
    result = {
        **evaluate_blind(tasks, export, seal["decisions"]),
        "sealed_decisions_sha256": seal_sha,
        "blind_export_sha256": export_sha,
        "blind_package_manifest_sha256": manifest_sha,
        "policy_commit": seal["policy_commit"],
        "interpretation": "Agreed outcomes require at least two distinct reviewer accounts.",
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
