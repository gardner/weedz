"""Make a sanitized, licensed demo copy; never open the live pilot for writes.

Outputs must be outside git. This is a curated capture subset, not a pilot evaluation.
"""

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any

from demo_paths import new_output, outside_git
from PIL import Image, ImageOps

ADMITTED = {"cc0", "cc-by"}


def completed_run(copied: sqlite3.Connection, requested: str | None) -> str:
    if requested is not None:
        row = copied.execute(
            "SELECT id FROM runs WHERE id=? AND status='completed'", (requested,)
        ).fetchone()
    else:
        row = copied.execute(
            "SELECT id FROM runs WHERE status='completed' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if row is None:
        raise ValueError("No matching completed run exists in the pilot")
    return str(row["id"])


def snapshot(source: Path, output: Path, run_id: str | None = None) -> dict[str, Any]:
    """Publish only a completed sanitized copy; raw backups stay in private temporary storage."""
    source, output = source.resolve(), new_output(output)
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Source and demo destinations must be independent")
    with tempfile.TemporaryDirectory(prefix="weedz-capture-private-") as private:
        staged = Path(private) / "snapshot"
        manifest = _build_snapshot(source, staged, run_id)
        output.parent.mkdir(parents=True, exist_ok=True)
        # Creation must succeed before the cleanup handler owns this path.
        output.mkdir(exist_ok=False)
        try:
            shutil.copytree(staged, output, dirs_exist_ok=True)
        except BaseException:
            shutil.rmtree(output)
            raise
    return manifest


def _build_snapshot(source: Path, output: Path, run_id: str | None) -> dict[str, Any]:
    """Sanitize a read-only backup inside the caller's private temporary directory."""
    output = outside_git(output)
    output.mkdir(parents=True, exist_ok=False)
    destination = output / "discovery.sqlite3"
    with (
        closing(sqlite3.connect(f"file:{source / 'discovery.sqlite3'}?mode=ro", uri=True)) as live,
        closing(sqlite3.connect(destination)) as copied,
    ):
        live.backup(copied)
    credits = []
    with closing(sqlite3.connect(destination)) as copied:
        copied.row_factory = sqlite3.Row
        copied.execute("PRAGMA journal_mode=DELETE")
        copied.execute("PRAGMA secure_delete=ON")
        run_id = completed_run(copied, run_id)
        # Remove human decisions/notes from the capture copy, never from the source.
        tables = copied.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        for table in tables:
            name = table["name"]
            if name not in {"runs", "photos"} and not name.startswith("sqlite_"):
                copied.execute(f'DELETE FROM "{name.replace(chr(34), chr(34) * 2)}"')
        copied.execute("DELETE FROM photos WHERE run_id<>?", (run_id,))
        copied.execute("DELETE FROM runs WHERE id<>?", (run_id,))
        for row in copied.execute("SELECT id, record, scores FROM photos").fetchall():
            record = json.loads(row["record"])
            if record["photo_license"] not in ADMITTED or not json.loads(row["scores"]):
                copied.execute("DELETE FROM photos WHERE id=?", (row["id"],))
                continue
            image = (source / record["image_path"]).resolve()
            if not image.is_relative_to(source / "images") or not image.is_file():
                raise ValueError("A source image must be within the pilot's public image cache")
            relative = Path("images") / f"{record['photo_id']}.png"
            target = output / relative
            target.parent.mkdir(exist_ok=True)
            with Image.open(image) as original:
                upright = ImageOps.exif_transpose(original).convert("RGB")
                clean = Image.new("RGB", upright.size)
                clean.paste(upright)
                clean.save(target)
            record.update(
                latitude=None,
                longitude=None,
                positional_accuracy_m=None,
                coordinate_status="missing",
                image_path=str(relative),
                sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            )
            copied.execute(
                "UPDATE photos SET record=?,review_status='unreviewed',review_note='',"
                "review_reviewer='' WHERE id=?",
                (json.dumps(record), row["id"]),
            )
            credits.append(
                {
                    "photo_id": row["id"],
                    "file": str(relative),
                    "creator_attribution": record["attribution"],
                    "license": record["photo_license"],
                    "license_url": "https://creativecommons.org/"
                    + (
                        "publicdomain/zero/1.0/"
                        if record["photo_license"] == "cc0"
                        else "licenses/by/4.0/"
                    ),
                    "source_url": record["source_url"],
                    "source_image_url": record["image_url"],
                    "cohort": record["cohort"],
                    "taxon": record.get("reference_species"),
                    "modifications": "Upright decoded pixels; lossless PNG; metadata removed.",
                }
            )
        copied.execute(
            "UPDATE runs SET detail=? WHERE id=?",
            ("DEMO: licensed public-photo subset; original scores; coordinates withheld", run_id),
        )
        copied.commit()
        copied.execute("VACUUM")
    if any(output.glob("discovery.sqlite3-*")):
        raise ValueError("Sanitized snapshot must be a standalone database without journal files")
    manifest = {
        "run": run_id,
        "disclosure": "Curated CC0/CC BY subset of a completed public pilot. Original screening "
        "scores, not a new evaluation. Review decisions are demonstration-only. "
        "Locations withheld.",
        "photos": credits,
    }
    (output / "capture-provenance.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pilot", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run")
    args = parser.parse_args()
    manifest = snapshot(args.source_pilot, args.output, args.run)
    print(json.dumps({"run": manifest["run"], "public_photos": len(manifest["photos"])}))


if __name__ == "__main__":
    main()
