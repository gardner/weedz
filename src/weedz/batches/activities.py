"""Versioned model and publication activities over exact canonical sample artifacts."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from temporalio import activity

from weedz.batches.compute import Computed, classify
from weedz.batches.contract import batch_request
from weedz.batches.package import Package, validate_package
from weedz.batches.package_build import build_package
from weedz.batches.profiles import ModelProfile
from weedz.batches.proposal_compute import segment
from weedz.batches.receipts import seal_file, write_receipt
from weedz.batches.regional_compute import regions
from weedz.batches.storage import ClosedBatch, read_artifact, read_owned_file, validate_closed_batch
from weedz.discovery.activities import while_heartbeating


@dataclass(frozen=True)
class BatchRegistry:
    segmentation: dict[str, ModelProfile]
    classifiers: dict[str, dict[str, ModelProfile]]

    def pins(self, request: dict) -> dict[str, str]:
        try:
            sam = self.segmentation[request["segmentation_profile"]]
            classifiers = self.classifiers[request["classifier_profile"]]
            selected = {kind: classifiers[kind] for kind in request["variants"]}
        except KeyError as error:
            raise ValueError("Requested inference profile is not registered") from error
        if any(profile.kind != kind for kind, profile in selected.items()):
            raise ValueError("Classifier profile kind disagrees with its registry entry")
        if "regions" in selected and not sam.matches(selected["regions"].metadata["proposer"]):
            raise ValueError("Regional classifier and segmentation profiles disagree")
        return {
            "proposals": sam.sha256,
            **{name: profile.sha256 for name, profile in selected.items()},
        }


@dataclass(frozen=True)
class Context:
    request: dict
    batch: ClosedBatch
    pins: dict[str, str]
    identity: str
    namespace: str
    completed: dict[str, dict]


class BatchActivities:
    def __init__(
        self,
        root: Path,
        registry: BatchRegistry,
        publisher: Callable[[Package, int], dict] | None = None,
    ) -> None:
        self.root, self.registry, self.publisher = root.resolve(), registry, publisher

    def _context(self, payload: dict) -> Context:
        request = batch_request(payload["request"])
        batch = validate_closed_batch(self.root, request["manifest"], request["ready"])
        pins = self.registry.pins(request)
        identity = hashlib.sha256(
            json.dumps(
                {"request": request, "profiles": pins}, sort_keys=True, allow_nan=False
            ).encode()
        ).hexdigest()
        completed = {}
        for name, reference in payload["completed"].items():
            record = json.loads(read_artifact(self.root, reference, 1024 * 1024))
            if record.get("stage") != name or record.get("identity") != identity:
                raise ValueError("Completed activity belongs to different inputs or profiles")
            completed[name] = record
        return Context(request, batch, pins, identity, f"temporal-batches/{identity}", completed)

    def _run(self, stage: str, payload: dict) -> dict:
        return while_heartbeating(lambda: self._execute(stage, payload), stage)

    def _execute(self, stage: str, payload: dict) -> dict:
        context = self._context(payload)
        path = f"{context.namespace}/{stage}.json"
        target = self.root / path
        if target.exists():
            encoded = read_owned_file(target, self.root, 1024 * 1024)
            previous = json.loads(encoded)
            if previous.get("identity") != context.identity or previous.get("stage") != stage:
                raise ValueError("Existing activity receipt has conflicting provenance")
            read_artifact(self.root, previous["artifact"], 128_000_000)
            seal_file(self.root, self.root / previous["artifact"]["path"])
            seal_file(self.root, target)
            if stage == "batch_package_v1":
                validate_package(
                    (self.root / previous["artifact"]["path"]).parent,
                    previous["artifact"]["sha256"],
                )
            return {"path": path, "sha256": hashlib.sha256(encoded).hexdigest()}
        result = self._dispatch(stage, context)
        read_artifact(self.root, result.artifact, 128_000_000)
        seal_file(self.root, self.root / result.artifact["path"])
        return write_receipt(
            self.root,
            path,
            {
                "schema": 1,
                "stage": stage,
                "identity": context.identity,
                "profiles": context.pins,
                "artifact": result.artifact,
                "origin": result.origin,
                "sample_count": len(context.batch.samples),
            },
        )

    def _artifact(self, context: Context, stage: str) -> dict:
        try:
            reference = context.completed[stage]["artifact"]
        except KeyError as error:
            raise ValueError("Required predecessor activity has not completed") from error
        read_artifact(self.root, reference, 128_000_000)
        return reference

    def _dispatch(self, stage: str, context: Context) -> Computed:
        request = context.request
        sam = self.registry.segmentation[request["segmentation_profile"]]
        classifiers = self.registry.classifiers[request["classifier_profile"]]
        cached = request["cached"]
        if stage == "batch_validate_v1":
            return Computed(request["manifest"], "activity-cache")
        self._artifact(context, "batch_validate_v1")
        if stage == "batch_segment_v1":
            return segment(
                self.root,
                context.batch,
                f"{context.namespace}/proposals",
                sam,
                external=cached.get("proposals"),
            )
        if stage == "batch_package_v1":
            inputs = {"proposals": self._artifact(context, "batch_segment_v1")}
            inputs.update(
                {
                    kind: self._artifact(context, f"batch_classify_{kind}_v1")
                    for kind in request["variants"]
                }
            )
            return Computed(
                build_package(self.root, context.batch, context.namespace, inputs),
                "temporal-activity",
            )
        if stage == "batch_publish_v1":
            return self._publish(context)
        kind = stage.removeprefix("batch_classify_").removesuffix("_v1")
        if kind not in request["variants"]:
            raise ValueError("Unexpected classifier stage")
        output = f"{context.namespace}/{kind}.json"
        if kind == "regions":
            return regions(
                self.root,
                context.batch,
                self._artifact(context, "batch_segment_v1"),
                output,
                classifiers[kind],
                sam,
                external=cached.get(kind),
            )
        return classify(
            self.root, context.batch, output, classifiers[kind], external=cached.get(kind)
        )

    def _publish(self, context: Context) -> Computed:
        if self.publisher is None:
            raise RuntimeError("Publication worker has not been configured")
        reference = self._artifact(context, "batch_package_v1")
        package = validate_package(
            (self.root / reference["path"]).parent,
            reference["sha256"],
            heartbeat=lambda: activity.heartbeat("verifying publication"),
        )
        result = self.publisher(package, context.request["project_id"])
        receipt = write_receipt(self.root, f"{context.namespace}/publication.json", result)
        return Computed(receipt, "temporal-activity")

    @activity.defn
    def batch_validate_v1(self, payload: dict) -> dict:
        return self._run("batch_validate_v1", payload)

    @activity.defn
    def batch_segment_v1(self, payload: dict) -> dict:
        return self._run("batch_segment_v1", payload)

    @activity.defn
    def batch_classify_frame_v1(self, payload: dict) -> dict:
        return self._run("batch_classify_frame_v1", payload)

    @activity.defn
    def batch_classify_tiles_v1(self, payload: dict) -> dict:
        return self._run("batch_classify_tiles_v1", payload)

    @activity.defn
    def batch_classify_regions_v1(self, payload: dict) -> dict:
        return self._run("batch_classify_regions_v1", payload)

    @activity.defn
    def batch_package_v1(self, payload: dict) -> dict:
        return self._run("batch_package_v1", payload)

    @activity.defn
    def batch_publish_v1(self, payload: dict) -> dict:
        return self._run("batch_publish_v1", payload)
