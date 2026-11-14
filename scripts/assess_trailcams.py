"""Summarise LILA's NZ trail-camera metadata to judge it as an incidental-weed source.

Usage: uv run python scripts/assess_trailcams.py <metadata.json> [--output summary.json]

Reads the COCO Camera Traps JSON published by LILA (no images are downloaded) and
reports licence-independent facts: sites, timestamps, daylight share, labels and
repetition per site. `daytime_sample` picks a reproducible frame per project for a
visual check of how much vegetation the cameras actually see.
"""

import argparse
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def _hour(image: dict[str, Any]) -> int | None:
    stamp = image.get("datetime") or ""
    return int(stamp[11:13]) if len(stamp) >= 13 and stamp[11:13].isdigit() else None


def summarise(data: dict[str, Any]) -> dict[str, Any]:
    images = data["images"]
    names = {category["id"]: category["name"] for category in data["categories"]}
    labels = Counter(names[annotation["category_id"]] for annotation in data["annotations"])
    per_site = sorted(Counter(image["location"] for image in images).values())
    hours = [hour for image in images if (hour := _hour(image)) is not None]
    years = Counter(image["datetime"][:4] for image in images if image.get("datetime"))
    return {
        "images": len(images),
        "projects": len({image["project"] for image in images}),
        "sites": len(per_site),
        "unknown_site_images": sum(image["location"].endswith("unknown") for image in images),
        "frames_per_site": {
            "median": statistics.median(per_site),
            "p90": per_site[int(len(per_site) * 0.9)],
            "max": per_site[-1],
        },
        "timestamped": len(hours),
        "daylight_07_19": sum(7 <= hour < 19 for hour in hours),
        "by_year": dict(sorted(years.items())),
        "top_labels": [[name, count] for name, count in labels.most_common(10)],
    }


def daytime_sample(data: dict[str, Any], per_project: int = 1) -> list[dict[str, Any]]:
    """A stable-hash pick of mid-day frames from known sites, `per_project` per project."""
    by_project: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for image in data["images"]:
        hour = _hour(image)
        if hour is not None and 9 <= hour < 16 and not image["location"].endswith("unknown"):
            by_project[image["project"]].append(image)
    picks = []
    for project in sorted(by_project):
        ranked = sorted(
            by_project[project], key=lambda i: hashlib.sha256(i["id"].encode()).digest()
        )
        picks += ranked[:per_project]
    return picks


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Summarise LILA NZ trail-camera metadata")
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    data = json.loads(args.metadata.read_text())
    summary = summarise(data) | {"daytime_sample": [i["id"] for i in daytime_sample(data)]}
    text = json.dumps(summary, indent=2)
    if args.output:
        args.output.write_text(text)
    else:
        print(text)


if __name__ == "__main__":
    main()
