"""Repeatable acquisition → GIS join → seasonality → standalone HTML."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from pipeline.cache import Acquisition, write_json
from pipeline.catalog import source_walks
from pipeline.download import acquire_walk
from pipeline.render import build
from pipeline.sources import ensure_sources


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument(
        "--snapshot", default="snapshot-v1", help="Existing/new named cached snapshot"
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Use a fresh dated snapshot, not old cache"
    )
    parser.add_argument("--first-year", type=int, default=2016)
    parser.add_argument("--last-year", type=int, default=2025)
    parser.add_argument("--radius-km", type=float, default=10)
    parser.add_argument("--render-only", action="store_true")
    args = parser.parse_args()
    if not 2000 <= args.first_year <= args.last_year < datetime.now(UTC).year:
        raise ValueError("Choose complete calendar years from 2000 onward")
    if Path(args.snapshot).name != args.snapshot:
        raise ValueError("Snapshot is a single directory name, not a path")
    name = datetime.now(UTC).strftime("snapshot-%Y%m%dT%H%M%SZ") if args.refresh else args.snapshot
    snapshot = args.data_root / name
    extra = args.data_root / "raw/gis-extra"
    ensure_sources(extra)
    if not args.render_only:
        config = {
            "first_year": args.first_year,
            "last_year": args.last_year,
            "radius_km": args.radius_km,
            "taxon_id": 47170,
            "policy": 1,
        }
        existing = snapshot / "config.json"
        if existing.exists() and json.loads(existing.read_text()) != config:
            raise ValueError("Configuration changed: use --refresh or a different --snapshot")
        write_json(existing, config)
        snapshot.chmod(0o700)
        client = Acquisition(snapshot / "requests")
        walks = source_walks(client, extra / "extra-walks.json")
        write_json(snapshot / "catalog.json", walks)
        for walk in walks:
            acquire_walk(
                client, walk, snapshot / "walks", args.first_year, args.last_year, args.radius_km
            )
        write_json(snapshot / "request-manifest.json", client.receipts)
    data = build(snapshot, extra, args.data_root / "site")
    print(
        json.dumps(
            {
                "output": str(args.data_root / "site/index.html"),
                "walks": len(data["walks"]),
                "unique_observations": data["unique_observations"],
            }
        )
    )


if __name__ == "__main__":
    run()
