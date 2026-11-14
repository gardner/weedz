"""Screen the same pilot and lookalike photos with each pinned model and compare them.

Usage:
  uv run python scripts/compare_models.py --pilot-dir data/pilot \
      --run nelson-tasman-3e62ad801459 --lookalikes <dir with result.json and images/> \
      --output benchmarks/model-comparison.json

Lookalikes are screened without a subject prompt, as in issue #11; pilot photos use the
same subject comparison as a real run. Source-labelled sanity checks, not accuracy.
"""

import argparse
import json
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


def summarise(rows: list[dict[str, Any]], seconds: float) -> dict[str, Any]:
    incidental = [row for row in rows if row["cohort"] == "incidental"]
    references = [row for row in rows if row["cohort"] == "reference"]
    lookalikes: dict[str, dict[str, int]] = defaultdict(lambda: {"top": 0, "positive": 0, "of": 0})
    for row in rows:
        if row["cohort"] != "lookalike":
            continue
        tally = lookalikes[row["lookalike_taxon"]]
        tally["of"] += 1
        tally["top"] += row["best_species"] == row["lookalike_of"]
        tally["positive"] += row["margins"].get(row["lookalike_of"], 0) > 0
    return {
        "incidental_positive": sum(max(row["margins"].values()) > 0 for row in incidental),
        "incidental_of": len(incidental),
        "references_own_target_top": [
            sum(row["best_species"] == row["reference_species"] for row in references),
            len(references),
        ],
        "lookalikes": dict(sorted(lookalikes.items())),
        "seconds_per_photo": round(seconds / max(1, len(rows)), 3),
    }


METHOD = (
    "Same 30 pilot photos (run nelson-tasman-3e62ad801459, with the original-subject "
    "comparison as in a real run) and 39 source-labelled lookalike photos (no subject "
    "prompt, as in #11), screened with ranking revision 4 (letterboxed frame plus square "
    "tiles) by each pinned model on CPU. Source-labelled sanity checks, not accuracy."
)
COMMAND = (
    "uv run python scripts/compare_models.py --run nelson-tasman-3e62ad801459 "
    "--lookalikes <lookalike dir> --output <file>"
)
ROW_KEYS = ["id", "cohort", "reference_species", "lookalike_taxon", "lookalike_of", "best_species"]


def document(results: dict[str, Any], assessed: str) -> dict[str, Any]:
    """The benchmark file exactly as committed: header, trimmed provenance, rows."""
    models = {}
    for key, result in results.items():
        rows = result["rows"]
        provenance = ["model", "model_key", "revision", "weights_sha256"]
        models[key] = {name: result["metadata"][name] for name in provenance} | {
            "summary": result["summary"],
            "reference_own_target_margins": [
                round(row["margins"][row["reference_species"]], 6)
                for row in rows
                if row["cohort"] == "reference"
            ],
            "rows": [
                {name: row.get(name) for name in ROW_KEYS}
                | {"margins": {n: round(v, 6) for n, v in row["margins"].items()}}
                for row in rows
            ],
        }
    return {
        "schema": 1,
        "assessed": assessed,
        "issue": "https://github.com/gardner/weedz/issues/14",
        "method": METHOD,
        "command": COMMAND,
        "models": models,
    }


def _row(base: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    margins = {item["name"]: item["margin"] for item in result["species"]}
    return base | {"best_species": result["best_species"], "margins": margins}


def screen_all(model: str, args: argparse.Namespace) -> dict[str, Any]:
    from weedz.discovery.inference import Screener, subject_label
    from weedz.discovery.store import Store

    screener = Screener.load(model=model)
    store = Store(args.pilot_dir)
    rows = []
    started = time.perf_counter()
    for photo in store.photos(args.run):
        result = screener.screen(store.root / photo["image_path"], subject_label(photo))
        rows.append(_row({k: photo.get(k) for k in ["id", "cohort", "reference_species"]}, result))
    for item in json.loads((args.lookalikes / "result.json").read_text())["photos"]:
        path = args.lookalikes / "images" / f"{item['id'].split('-')[-1]}.jpg"
        base = {"id": item["id"], "cohort": "lookalike"} | {
            key: item[key] for key in ["lookalike_taxon", "lookalike_of"]
        }
        rows.append(_row(base, screener.screen(path)))
    elapsed = time.perf_counter() - started
    return {"metadata": screener.metadata, "summary": summarise(rows, elapsed), "rows": rows}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Compare pinned screening models")
    parser.add_argument("--pilot-dir", type=Path, default=Path("data/pilot"))
    parser.add_argument("--run", required=True)
    parser.add_argument("--lookalikes", type=Path, required=True)
    parser.add_argument("--models", nargs="+", default=["bioclip", "bioclip-2"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    results = {model: screen_all(model, args) for model in args.models}
    output = document(results, date.today().isoformat())
    args.output.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
    for model, result in results.items():
        print(model, json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
