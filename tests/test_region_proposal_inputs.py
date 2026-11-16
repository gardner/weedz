"""New label revisions may join old inference only through unchanged source pixels."""

import hashlib
import json
from pathlib import Path

import pytest
from region_helpers import sample

from weedz.region_evaluation.proposal_inputs import load_proposals


def source(root: Path, rows: list[dict] | None = None) -> str:
    row = {
        "sample_id": "cwfid:1",
        "image_sha256": "a" * 64,
        "model_version": "sam:v1",
        "segmentation": {"status": "empty", "regions": [], "provenance": {"model": "sam"}},
    }
    encoded = "".join(
        json.dumps(value) + "\n" for value in (rows if rows is not None else [row])
    ).encode()
    (root / "proposals.jsonl").write_bytes(encoded)
    ready = json.dumps(
        {
            "schema": 1,
            "count": len(encoded.splitlines()),
            "manifest_sha256": "b" * 64,
            "model_version": "sam:v1",
            "proposals_sha256": hashlib.sha256(encoded).hexdigest(),
        }
    ).encode()
    (root / "ready.json").write_bytes(ready)
    return hashlib.sha256(ready).hexdigest()


def test_labels_can_change_without_reheadering_old_inference(tmp_path: Path) -> None:
    checksum = source(tmp_path)
    batch = load_proposals(tmp_path / "ready.json", checksum, [sample()])
    assert batch.manifest_sha256 == "b" * 64
    assert batch.rows["cwfid:1"]["image_sha256"] == "a" * 64


def test_changed_pixels_cannot_inherit_proposals(tmp_path: Path) -> None:
    checksum = source(tmp_path)
    changed = sample(media={"uri": "1.png", "sha256": "c" * 64, "width": 10, "height": 10})
    with pytest.raises(ValueError, match="media"):
        load_proposals(tmp_path / "ready.json", checksum, [changed])


def test_replaced_rows_refused_by_closed_digest(tmp_path: Path) -> None:
    checksum = source(tmp_path)
    (tmp_path / "proposals.jsonl").write_text("{}\n")
    with pytest.raises(ValueError, match="checksum"):
        load_proposals(tmp_path / "ready.json", checksum, [sample()])


def test_missing_and_duplicate_rows_do_not_disappear_from_denominators(tmp_path: Path) -> None:
    checksum = source(tmp_path, [])
    with pytest.raises(ValueError, match="count"):
        load_proposals(tmp_path / "ready.json", checksum, [sample()])
    source(tmp_path)
    row = json.loads((tmp_path / "proposals.jsonl").read_text())
    checksum = source(tmp_path, [row, row])
    with pytest.raises(ValueError, match="duplicate"):
        load_proposals(
            tmp_path / "ready.json", checksum, [sample(), sample(id="cwfid:2", source_id="2")]
        )


def test_unpinned_media_cannot_be_an_evaluation_identity(tmp_path: Path) -> None:
    source(tmp_path)
    row = json.loads((tmp_path / "proposals.jsonl").read_text())
    row["image_sha256"] = None
    checksum = source(tmp_path, [row])
    unpinned = sample(media={"uri": "1.png", "width": 10, "height": 10})
    with pytest.raises(ValueError, match="pinned"):
        load_proposals(tmp_path / "ready.json", checksum, [unpinned])
