"""Durable model stages: completed matching evidence survives activity interruption."""

import base64
import io
import json
import time
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from weedz.discovery.inference import file_sha256, subject_label
from weedz.discovery.records import RunSpec
from weedz.discovery.store import Store
from weedz.segmentation.artifacts import StageArtifacts
from weedz.segmentation.pipeline import Proposer, identify_views
from weedz.segmentation.regions import ProposalConfig, proposals, upright

PROFILE = "sam2.1-tiny-v1"
CONFIG = ProposalConfig()
RETRYABLE = (RuntimeError, OSError, MemoryError)


class PipelineStages:
    def __init__(
        self,
        store: Store,
        proposer: Callable[[], Proposer],
        screener: Callable[[str], Any],
        heartbeat: Callable[[str], None],
        work: Callable[[Callable[[], Any], str], Any] = lambda action, _detail: action(),
    ) -> None:
        self.store, self.proposer, self.screener = store, proposer, screener
        self.heartbeat, self.work = heartbeat, work

    def _retry_photo(self, action: Callable[[], Any], detail: str) -> Any:
        for attempt in range(3):
            try:
                return action()
            except RETRYABLE:
                if attempt == 2:
                    raise
                self.heartbeat(f"Retrying {detail}: attempt {attempt + 2} of 3")
                time.sleep(0.1 * (attempt + 1))

    def _generate(self, path: Path, proposer: Proposer) -> list:
        image = upright(path)
        return proposals(
            image, self.work(lambda: proposer.generate(image), "SAM generation"), CONFIG
        )

    def _photos(self, run_id: str) -> list[dict]:
        run = next(item for item in self.store.runs() if item["id"] == run_id)
        if RunSpec.from_saved(run["spec"]).segmentation != PROFILE:
            raise ValueError("Run does not request the versioned segmentation profile")
        return self.store.photos(run_id)

    def _path(self, photo: dict) -> Path:
        path = (self.store.root / photo["image_path"]).resolve()
        if (
            not path.is_relative_to(self.store.root.resolve())
            or file_sha256(path) != photo["sha256"]
        ):
            raise ValueError("Source image provenance changed")
        return path

    def segment(self, run_id: str) -> dict:
        photos = self._photos(run_id)
        proposer = self.proposer()  # Startup/checkpoint/config errors must fail the activity.
        artifacts = StageArtifacts(self.store.root, run_id)
        count = {"schema": 1, "count": len(photos), "completed": 0, "failed": 0, "cache_hits": 0}
        for photo in photos:
            self.heartbeat(f"segmenting {photo['id']}")
            path = self._path(photo)
            inputs = {
                "profile": PROFILE,
                "image_sha256": photo["sha256"],
                "config": asdict(CONFIG),
                "proposer": proposer.metadata,
            }
            previous = artifacts.read("proposals", photo["id"], inputs)
            if previous and previous["status"] in {"ok", "empty"}:
                count["cache_hits"] += 1
                count["completed"] += 1
                continue
            start = time.monotonic()
            result: dict[str, Any] = {"regions": []}
            try:
                regions = self._retry_photo(
                    lambda path=path: self._generate(path, proposer), f"SAM photo {photo['id']}"
                )
                result.update(
                    status="ok" if regions else "empty",
                    regions=[region.record() for region in regions],
                )
            except (ValueError, *RETRYABLE) as error:
                result.update(status="failed", failure_type=type(error).__name__)
                result = artifacts.write("proposals", photo["id"], inputs, result)
            result["elapsed_seconds"] = time.monotonic() - start
            result = artifacts.write("proposals", photo["id"], inputs, result)
            count["failed" if result["status"] == "failed" else "completed"] += 1
            self.store.status(
                run_id,
                "screening",
                f"SAM proposals: {count['completed']} completed; "
                f"{count['failed']} failed (baseline fallback)",
            )
        return count

    def _proposal(self, artifacts: StageArtifacts, photo: dict) -> dict:
        record = artifacts.entry("proposals", photo["id"])
        if record is None:
            raise ValueError("Proposal stage has not committed this photo")
        expected = {"profile": PROFILE, "image_sha256": photo["sha256"], "config": asdict(CONFIG)}
        if any(record["inputs"].get(key) != value for key, value in expected.items()):
            raise ValueError("Proposal provenance changed; start a new run")
        return record

    def score_regions(self, run_id: str) -> dict:
        photos = self._photos(run_id)
        model = self.screener(run_id)
        artifacts = StageArtifacts(self.store.root, run_id)
        count = {"schema": 1, "count": len(photos), "completed": 0, "failed": 0, "cache_hits": 0}
        for photo in photos:
            self.heartbeat(f"scoring proposal views {photo['id']}")
            path = self._path(photo)
            if not photo["scores"]:
                raise ValueError("Full-frame/tile baseline must complete before region scoring")
            proposal = self._proposal(artifacts, photo)
            inputs = {
                "proposal_sha256": proposal["sha256"],
                "classifier": model.metadata,
                "version": 1,
            }
            evidence = artifacts.read("views", photo["id"], inputs)
            if evidence and evidence["view_status"] in {"ok", "empty"}:
                count["cache_hits"] += 1
            else:
                evidence = self._views(path, photo, proposal, model, artifacts, inputs)
            self._attach(run_id, photo["id"], evidence)
            count["failed" if evidence["status"] == "failed" else "completed"] += 1
        return count

    def _views(
        self,
        path: Path,
        photo: dict,
        proposal: dict,
        model: Any,
        artifacts: StageArtifacts,
        inputs: dict,
    ) -> dict:
        result = proposal["result"]
        evidence = {
            **result,
            "schema": 1,
            "proposal_status": result["status"],
            "baseline_retained": True,
            "coordinate_frame": "EXIF-upright original; xyxy right/bottom exclusive",
            "provenance": {"proposal": proposal["inputs"], "classification": inputs},
        }
        evidence["view_status"] = (
            "skipped_proposal_failure" if result["status"] == "failed" else "empty"
        )
        if result["status"] == "ok":
            try:
                evidence["regions"] = self._retry_photo(
                    lambda: self._classified_regions(path, result, model, photo),
                    f"region classification {photo['id']}",
                )
                evidence["view_status"] = "ok"
            except (ValueError, *RETRYABLE) as error:
                evidence["regions"] = [{**row, "views": {}} for row in result["regions"]]
                evidence.update(
                    status="failed", view_status="failed", failure_type=type(error).__name__
                )
                evidence = artifacts.write("views", photo["id"], inputs, evidence)
        return artifacts.write("views", photo["id"], inputs, evidence)

    def _classified_regions(self, path: Path, result: dict, model: Any, photo: dict) -> list:
        regions = restored_regions(upright(path), result["regions"])
        return [
            {
                **region.record(),
                "views": self.work(
                    lambda region=region: identify_views(model, region.views, subject_label(photo)),
                    "BioCLIP region scoring",
                ),
            }
            for region in regions
        ]

    def _attach(self, run_id: str, photo_id: str, evidence: dict) -> None:
        with self.store.connect() as db:
            db.execute(
                "UPDATE photos SET scores=json_set(scores, '$.segmentation', json(?)) "
                "WHERE run_id=? AND id=? AND (? OR "
                "COALESCE(json_extract(scores, '$.segmentation.view_status'), '') "
                "NOT IN ('ok', 'empty'))",
                (
                    json.dumps(evidence),
                    run_id,
                    photo_id,
                    evidence.get("view_status") in {"ok", "empty"},
                ),
            )

    def summary(self, run_id: str) -> dict:
        from weedz.segmentation.summary import pipeline_summary

        result = pipeline_summary(self.store, run_id)
        if result is None:
            raise ValueError("Segmentation was not requested")
        return result


def restored_regions(image: Image.Image, records: list[dict]) -> list:
    if len(records) > CONFIG.max_proposals:
        raise ValueError("Proposal count exceeds profile cap")
    raw = []
    for record in records:
        encoded = record["mask_png"]
        if len(encoded) > 1_000_000:
            raise ValueError("Mask exceeds profile cap")
        with Image.open(io.BytesIO(base64.b64decode(encoded, validate=True))) as mask:
            if max(mask.size) > CONFIG.max_side or mask.mode != "RGBA":
                raise ValueError("Invalid proposal mask geometry")
            raw.append(
                {"segmentation": np.asarray(mask.getchannel("A")) > 0, **record["mask_quality"]}
            )
    result = proposals(image, raw, CONFIG)
    if [region.record() for region in result] != records:
        raise ValueError("Proposal transforms or mask provenance changed")
    return result
