"""Join Label Studio JSON submissions to frozen pilot tasks and summarize effort."""

import argparse
import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from statistics import median
from typing import Any

Row = dict[str, Any]
PRESENCE = {"Watchlist plant visible", "No watchlist plant visible", "Unsure"}


def _positive_id(value: Any) -> int:
    if type(value) is not int or value < 1:
        raise ValueError("Expected a positive Label Studio identifier")
    return value


def _seconds(value: Any) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("Invalid lead time")
    return float(value) if value > 0 else None


def _watchlist_answer(results: list[Row]) -> str:
    relevant = [row for row in results if row.get("from_name") == "watchlist_presence"]
    if not relevant:
        return "Missing answer"
    if len(relevant) != 1:
        raise ValueError("Duplicate watchlist presence answer")
    row = relevant[0]
    values = row.get("value", {}).get("choices")
    if row.get("type") != "choices" or row.get("to_name") != "image":
        raise ValueError("Invalid watchlist presence control")
    if not isinstance(values, list) or len(values) != 1 or values[0] not in PRESENCE:
        raise ValueError("Invalid watchlist presence answer")
    return values[0]


@dataclass
class Effort:
    annotations: set[int] = field(default_factory=set)
    reviewers: set[int] = field(default_factory=set)
    answered_tasks: set[int] = field(default_factory=set)
    seconds: list[float] = field(default_factory=list)
    answers: Counter[str] = field(default_factory=Counter)
    cancelled: int = 0
    ground_truth: int = 0

    def add(self, annotation: Row, task_id: int) -> None:
        identity = _positive_id(annotation.get("id"))
        if identity in self.annotations:
            raise ValueError("Duplicate annotation in pilot export")
        self.annotations.add(identity)
        if annotation.get("task") != task_id:
            raise ValueError("Annotation task identity differs from export task")
        if type(annotation.get("was_cancelled")) is not bool:
            raise ValueError("Pilot annotations must declare cancellation status")
        if annotation["was_cancelled"]:
            self.cancelled += 1
            return
        if annotation.get("ground_truth") is True:
            self.ground_truth += 1
            return
        reviewer = annotation.get("completed_by")
        self.reviewers.add(_positive_id(reviewer["id"] if isinstance(reviewer, dict) else reviewer))
        self.answered_tasks.add(task_id)
        self.answers[_watchlist_answer(annotation["result"])] += 1
        if (seconds := _seconds(annotation.get("lead_time"))) is not None:
            self.seconds.append(seconds)

    def report(self, planned: int, exported: int) -> Row:
        submissions = self.answers.total()
        return {
            "planned_tasks": planned,
            "exported_tasks": exported,
            "tasks_with_submission": len(self.answered_tasks),
            "submissions": submissions,
            "reviewers": len(self.reviewers),
            "cancelled_annotations": self.cancelled,
            "ground_truth_annotations": self.ground_truth,
            "watchlist_answers": dict(sorted(self.answers.items())),
            "timed_submissions": len(self.seconds),
            "untimed_submissions": submissions - len(self.seconds),
            "total_seconds": sum(self.seconds),
            "median_seconds": median(self.seconds) if self.seconds else None,
        }


def _identity(task: Row) -> str:
    key = task.get("meta", {}).get("external_id")
    if not isinstance(key, str) or not key:
        raise ValueError("Every pilot task needs its original external ID")
    return key


def _bound_task(exported: Row, planned: dict[str, Row]) -> str:
    key = _identity(exported)
    task = planned.get(key)
    if task is None or any(exported.get(field) != task[field] for field in ("data", "meta")):
        raise ValueError("Exported task data and metadata must match the package")
    return key


def summarize(package_tasks: list[Row], export: list[Row]) -> Row:
    """Report submission timing and answers. This does not adjudicate botanical truth."""
    planned = {_identity(task): task for task in package_tasks}
    if len(planned) != len(package_tasks):
        raise ValueError("Duplicate external ID in pilot package")
    seen_keys: set[str] = set()
    seen_ids: set[int] = set()
    effort = Effort()
    for task in export:
        key = _bound_task(task, planned)
        task_id = _positive_id(task.get("id"))
        if key in seen_keys or task_id in seen_ids:
            raise ValueError("Duplicate task in pilot export")
        seen_keys.add(key)
        seen_ids.add(task_id)
        for annotation in task["annotations"]:
            effort.add(annotation, task_id)
    return effort.report(len(planned), len(seen_keys))


def _load(path: Path) -> tuple[Any, str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _package(root: Path) -> tuple[list[Row], str]:
    manifest, digest = _load(root / "manifest.json")
    tasks, tasks_digest = _load(root / "tasks.json")
    if tasks_digest != manifest["files"]["tasks.json"] or len(tasks) != manifest["task_count"]:
        raise ValueError("Pilot task checksum or count differs from its manifest")
    return tasks, digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for arm in ("blind", "assisted"):
        parser.add_argument(f"--{arm}-package", type=Path, required=True)
        parser.add_argument(f"--{arm}-export", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blind_tasks, blind_manifest = _package(args.blind_package)
    assisted_tasks, assisted_manifest = _package(args.assisted_package)
    blind_sha = {task["meta"]["image_sha256"] for task in blind_tasks}
    assisted_sha = {task["meta"]["image_sha256"] for task in assisted_tasks}
    if blind_sha & assisted_sha:
        raise ValueError("Blind and assisted packages share source images")
    blind_export, blind_export_sha = _load(args.blind_export)
    assisted_export, assisted_export_sha = _load(args.assisted_export)
    output = {
        "blind": summarize(blind_tasks, blind_export),
        "assisted": summarize(assisted_tasks, assisted_export),
        "inputs": {
            "blind_package_manifest_sha256": blind_manifest,
            "assisted_package_manifest_sha256": assisted_manifest,
            "blind_export_sha256": blind_export_sha,
            "assisted_export_sha256": assisted_export_sha,
        },
        "interpretation": "Different images per arm. Lead times are descriptive per submission.",
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
