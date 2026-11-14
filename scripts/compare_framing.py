"""Compare whole-frame and tile screening at fixed reviewer budgets (issue #12).

Usage:
  uv run python scripts/compare_framing.py --pilot-dir data/pilot \
      --run nelson-tasman-3e62ad801459 --lookalikes <dir with result.json and images/> \
      --output benchmarks/whole-vs-region.json

Each photo is screened once (embeddings cached under <pilot-dir>/embeddings); the arms
are readouts of those same window similarities (weedz.discovery.framing). Independent
labels come from the run's reference collection and blind audits; reference and
lookalike photos add source subject labels, which are never pooled with them.
"""

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from weedz.discovery.framing import compare

BUDGETS = [5, 10, 20]
METHOD = (
    "One ranking revision 4 screen per photo (pinned model, CPU), read three ways from the "
    "same window similarities: whole frame only, tiles only, and both (what runs use). "
    "Each arm ranks photos by best margin; a reviewer budget K is the top K photos. The "
    "incidental queue is measured against independent labels (evaluation-eligible "
    "reference-collection examples and agreeing blind audits, both on the rank-"
    "independent blind audit sample only); a pooled queue of "
    "incidental, reference and lookalike photos is measured against source subject labels "
    "and counts lookalikes reaching the budget as the weed they resemble. Lookalikes are "
    "screened without a subject prompt, as in #11; pilot photos with it, as in a run."
)
COMMAND = (
    "uv run python scripts/compare_framing.py --run nelson-tasman-3e62ad801459 "
    "--lookalikes <lookalike dir> --output benchmarks/whole-vs-region.json"
)
PROVENANCE = ["model", "model_key", "revision", "weights_sha256"]


def conclusion(labels: dict[str, int]) -> str:
    """What the file can conclude, from the labels it was measured against."""
    if not labels["independent"]:
        return (
            "No independently reviewed background-plant labels exist, so incidental recall "
            "and precision are not measurable and this file cannot say whether whole-frame "
            "or tile screening finds more useful weeds. The source subject and lookalike "
            "measures concern photos whose subject is the plant; they are sanity checks of "
            "each arm, not background-plant evidence. Arm overlap shows how much the choice "
            "changes what a reviewer would see."
        )
    return (
        f"Measured against {labels['independent']} independent labels on the incidental "
        "queue; small label counts bound rather than estimate recall and precision. "
        "Source subject measures remain sanity checks, never pooled with them."
    )


def _rounded(found: dict[str, Any] | None) -> dict[str, Any] | None:
    return found and {"species": found["species"], "margin": round(found["margin"], 6)}


def document(
    comparison: dict[str, Any],
    metadata: dict[str, Any],
    inputs: dict[str, Any],
    assessed: str,
    cohorts: dict[str, str],
) -> dict[str, Any]:
    """The benchmark file exactly as committed; each photo with its cohort and arms."""
    photos = {
        pid: {"cohort": cohorts.get(pid)} | {arm: _rounded(found) for arm, found in arms.items()}
        for pid, arms in comparison["photos"].items()
    }
    return {
        "schema": 1,
        "assessed": assessed,
        "issue": "https://github.com/gardner/weedz/issues/12",
        "method": METHOD,
        "command": COMMAND,
        "model": {name: metadata[name] for name in PROVENANCE},
        "inputs": inputs,
        "conclusion": conclusion(comparison["labels"]),
        **{key: value for key, value in comparison.items() if key != "photos"},
        "photos": photos,
    }


def lookalike_photos(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "cohort": "lookalike",
            "lookalike_taxon": item["lookalike_taxon"],
            "lookalike_of": item["lookalike_of"],
            "image": f"images/{item['id'].split('-')[-1]}.jpg",
        }
        for item in items
    ]


def screen_all(args: argparse.Namespace) -> dict[str, Any]:
    from weedz.adapters import pilot_samples
    from weedz.discovery.audit import audit_sample
    from weedz.discovery.framing import independent_labels
    from weedz.discovery.inference import Screener, subject_label
    from weedz.discovery.store import Store
    from weedz.reference import examples

    screener = Screener.load(args.pilot_dir / "embeddings", model=args.model)
    store = Store(args.pilot_dir)
    pilot = store.photos(args.run)
    looks = lookalike_photos(json.loads((args.lookalikes / "result.json").read_text())["photos"])
    results = {
        photo["id"]: screener.screen(store.root / photo["image_path"], subject_label(photo))
        for photo in pilot
    } | {photo["id"]: screener.screen(args.lookalikes / photo["image"]) for photo in looks}
    labels = independent_labels(
        examples(pilot_samples(store, args.run)),
        store.latest_audits(args.run),
        audit_sample(args.run, pilot),
    )
    photos = [*pilot, *looks]
    comparison = compare(results, photos, labels, BUDGETS)
    inputs = {"run": args.run, "pilot_photos": len(pilot), "lookalike_photos": len(looks)}
    cohorts = {photo["id"]: photo["cohort"] for photo in photos}
    return document(comparison, screener.metadata, inputs, date.today().isoformat(), cohorts)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compare whole-frame and tile screening")
    parser.add_argument("--pilot-dir", type=Path, default=Path("data/pilot"))
    parser.add_argument("--run", required=True)
    parser.add_argument("--lookalikes", type=Path, required=True)
    parser.add_argument("--model", default="bioclip-2", choices=["bioclip", "bioclip-2"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = screen_all(args)
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    for arm, report in output["arms"].items():
        print(arm, json.dumps(report["pooled"]["budgets"]))


if __name__ == "__main__":
    main()
