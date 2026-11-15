"""Seed a NEW private review store from licensed logical records, never raw SQLite pages."""

import argparse
import hashlib
import io
import json
import shutil
import sqlite3
import tempfile
from collections import Counter
from contextlib import closing
from pathlib import Path

from PIL import Image, ImageOps

from weedz.discovery.records import Photo, RunSpec
from weedz.discovery.store import Store

HOSTED_LICENCES = {"cc0", "cc-by"}


def _validate_hosting_licences(rows: list[sqlite3.Row]) -> None:
    unsupported: Counter[str] = Counter()
    for row in rows:
        if json.loads(row["scores"]):
            licence = Photo.model_validate_json(row["record"]).photo_license
            if licence not in HOSTED_LICENCES:
                unsupported[licence] += 1
    if unsupported:
        count = sum(unsupported.values())
        details = ", ".join(
            f"{licence}={amount}" for licence, amount in sorted(unsupported.items())
        )
        raise ValueError(
            f"Hosted policy admits CC0/CC BY only; {count} scored photo records have unsupported "
            f"licences: {details}. No photos were imported."
        )


def seed(source: Path, output: Path, run_id: str) -> int:
    source, output = source.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError("Choose a new independent data directory")
    with closing(sqlite3.connect(f"file:{source / 'discovery.sqlite3'}?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        run = db.execute(
            "SELECT * FROM runs WHERE id=? AND status='completed'", (run_id,)
        ).fetchone()
        if run is None:
            raise ValueError("Choose an existing completed source run")
        rows = db.execute(
            "SELECT record,scores,screened_at FROM photos WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
    _validate_hosting_licences(rows)
    with tempfile.TemporaryDirectory(prefix="weedz-site-seed-") as temporary:
        staged = Path(temporary) / "data"
        staged.mkdir(mode=0o700)
        target = Store(staged)
        target.create_run(run_id, RunSpec.from_saved(json.loads(run["spec"])))
        with closing(sqlite3.connect(target.database)) as copied, copied:
            copied.execute("UPDATE runs SET created_at=? WHERE id=?", (run["created_at"], run_id))
        target.model(run_id, json.loads(run["model"]))
        count = 0
        for row in rows:
            photo = Photo.model_validate_json(row["record"])
            scores = json.loads(row["scores"])
            if not scores:
                continue
            sanitized = _copy_photo(source, staged, photo)
            target.save_photos(run_id, [sanitized])
            target.score(run_id, sanitized.id, scores)
            with closing(sqlite3.connect(target.database)) as copied, copied:
                copied.execute(
                    "UPDATE photos SET screened_at=? WHERE run_id=? AND id=?",
                    (row["screened_at"], run_id, sanitized.id),
                )
            count += 1
        if not count:
            raise ValueError("Source run has no admitted scored public photos")
        target.status(
            run_id, "completed", "Licensed source evidence; original scores; new review history"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir(mode=0o700, exist_ok=False)
        try:
            shutil.copytree(staged, output, dirs_exist_ok=True)
        except BaseException:
            shutil.rmtree(output)
            raise
    return count


def _copy_photo(source: Path, staged: Path, photo: Photo) -> Photo:
    image = (source / photo.image_path).resolve()
    if not image.is_relative_to(source / "images") or not image.is_file():
        raise ValueError("Source image escapes the public cache")
    raw = image.read_bytes()
    if hashlib.sha256(raw).hexdigest() != photo.sha256:
        raise ValueError("Source image differs from its licensed provenance")
    relative = Path("images") / f"{photo.photo_id}.png"
    destination = staged / relative
    destination.parent.mkdir(exist_ok=True)
    with Image.open(io.BytesIO(raw)) as original:
        if original.width * original.height > 40_000_000:
            raise ValueError("Source image exceeds 40 megapixels")
        pixels = ImageOps.exif_transpose(original).convert("RGB")
        clean = Image.new("RGB", pixels.size)
        clean.paste(pixels)
        clean.save(destination)
    return photo.model_copy(
        update={
            "image_path": str(relative),
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "latitude": None,
            "longitude": None,
            "positional_accuracy_m": None,
            "coordinate_status": "missing",
            "observed_on": None,
            "uploaded_at": None,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    count = seed(args.source, args.output, args.run)
    print(f"Seeded {count} licensed photos into a new private store")


if __name__ == "__main__":
    main()
