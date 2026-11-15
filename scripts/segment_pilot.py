"""Create an isolated public-photo segmentation experiment, never update a source run."""

import argparse
import hashlib
import json
import resource
import sqlite3
import sys
import time
from pathlib import Path

from weedz.discovery.inference import Screener, subject_label
from weedz.discovery.records import Photo, RunSpec
from weedz.discovery.store import Store
from weedz.segmentation.pipeline import SegmentedScreen
from weedz.segmentation.regions import ProposalConfig, upright
from weedz.segmentation.sam2 import CHECKPOINT_SHA256, Sam2Proposer


def public_photos(source: Path, run_id: str, limit: int) -> list[Photo]:
    with sqlite3.connect(f"file:{source / 'discovery.sqlite3'}?mode=ro", uri=True) as db:
        rows = db.execute("SELECT record FROM photos WHERE run_id=? ORDER BY id", (run_id,))
        photos = [Photo.model_validate_json(row[0]) for row in rows]
    eligible = [p for p in photos if p.photo_license in {"cc-by", "cc0"}]
    # Clear coordinates and dates in the independent visual experiment; source stays untouched.
    return [
        p.model_copy(
            update={
                "latitude": None,
                "longitude": None,
                "observed_on": None,
                "positional_accuracy_m": None,
                "coordinate_status": "missing",
            }
        )
        for p in eligible[:limit]
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-run", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=6, choices=range(1, 31))
    parser.add_argument("--device", choices=["cpu", "cuda:0"], default="cuda:0")
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if output.exists() or output == source or output.is_relative_to(source):
        raise ValueError("Choose a new independent output directory outside the source")
    # Outputs must not be placed within this source checkout or any ancestor git worktree.
    if any((parent / ".git").exists() for parent in [output, *output.parents]):
        raise ValueError("Model outputs must stay outside Git")
    photos = public_photos(source, args.source_run, args.limit)
    if not photos:
        raise ValueError("No eligible public photos in that source run")
    output.mkdir(parents=True)
    store = Store(output)
    run_id = "segmentation-experiment-v1"
    config = ProposalConfig()
    proposer = Sam2Proposer(
        args.checkpoint, CHECKPOINT_SHA256, output / "masks-cache", config, args.device
    )
    baseline = Screener.load(output / "embeddings", model="bioclip-2")
    screener = SegmentedScreen(baseline, proposer, config)
    store.create_run(run_id, RunSpec(model="bioclip-2"))
    store.model(run_id, screener.metadata)
    measurements = []
    for photo in photos:
        original = (source / photo.image_path).resolve()
        if not original.is_relative_to(source):
            raise ValueError("Source image escapes public pilot")
        if hashlib.sha256(original.read_bytes()).hexdigest() != photo.sha256:
            raise ValueError("Source photo checksum mismatch")
        destination = output / "images" / f"{photo.photo_id}.png"
        destination.parent.mkdir(exist_ok=True)
        pixels = upright(original)
        pixels.info.clear()
        pixels.save(destination, format="PNG")
        photo = photo.model_copy(
            update={
                "image_path": str(destination.relative_to(output)),
                "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            }
        )
        store.save_photos(run_id, [photo])
        proposer.torch.cuda.reset_peak_memory_stats() if args.device.startswith("cuda") else None
        start = time.monotonic()
        scores = screener.screen(destination, subject_label(photo.model_dump()))
        store.score(run_id, photo.id, scores)
        measurements.append(
            {
                "id": photo.id,
                "source_url": photo.source_url,
                "attribution": photo.attribution,
                "licence": photo.photo_license,
                "elapsed_seconds": time.monotonic() - start,
                "proposal_count": len(scores["segmentation"]["regions"]),
                "status": scores["segmentation"]["status"],
                "gpu_peak_bytes": proposer.torch.cuda.max_memory_allocated()
                if args.device.startswith("cuda")
                else None,
            }
        )
        print(json.dumps(measurements[-1]), flush=True)
    store.status(run_id, "completed", "Opt-in class-agnostic proposals; baseline ranking retained")
    (output / "experiment.json").write_text(
        json.dumps(
            {
                "measurements": measurements,
                "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                "provenance": screener.metadata,
                "python": sys.version,
                "ground_truth": (
                    "No independent background-plant masks; no recall or confidence claim"
                ),
            },
            indent=2,
        )
    )
    print(output)


if __name__ == "__main__":
    main()
