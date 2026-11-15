"""Real frame/tiles execution or explicit, fully checked external artifact adoption."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

from weedz.batches.contract import artifact
from weedz.batches.profiles import ModelProfile
from weedz.batches.storage import ClosedBatch, read_artifact, read_owned_file
from weedz.classification.batch import classify_batch


@dataclass(frozen=True)
class Computed:
    artifact: dict[str, str]
    origin: Literal["external-compute", "activity-cache", "temporal-activity"]


class MetadataOnlyClassifier:
    def __init__(self, metadata: dict[str, Any]) -> None:
        self.metadata = metadata

    def predict(self, *_args, **_kwargs) -> list[list[dict]]:
        raise RuntimeError("Adopting a completed artifact must never invoke inference")


def _existing_model(root: Path, reference: dict, profile: ModelProfile) -> MetadataOnlyClassifier:
    document = json.loads(read_artifact(root, reference, 128_000_000))
    if not isinstance(document, dict) or not isinstance(document.get("model"), dict):
        raise ValueError("Invalid classifier artifact metadata")
    if not profile.matches(document["model"]):
        raise ValueError("Classifier artifact disagrees with its registered profile")
    return MetadataOnlyClassifier(document["model"])


def classify(
    root: Path,
    batch: ClosedBatch,
    relative_output: str,
    profile: ModelProfile,
    *,
    external: dict[str, str] | None = None,
) -> Computed:
    read_artifact(
        root,
        {
            "path": str(batch.manifest.relative_to(root.resolve())),
            "sha256": batch.sha256,
        },
        32 * 1024 * 1024,
    )
    if profile.kind not in {"frame", "tiles"}:
        raise ValueError("This runner supports frame or tiles classifier profiles")
    if external is not None:
        reference = artifact(external)
        model = _existing_model(root, reference, profile)
        output = root / reference["path"]
        origin = "external-compute"
    else:
        reference = artifact({"path": relative_output, "sha256": "0" * 64})
        output = root / reference["path"]
        if output.resolve().is_relative_to(batch.manifest.parent):
            raise ValueError("Classifier output must remain independent of closed source storage")
        if not output.resolve().is_relative_to(root.resolve()):
            raise ValueError("Classifier output escapes owned storage")
        if output.exists():
            reference["sha256"] = hashlib.sha256(
                read_owned_file(output, root, 128_000_000)
            ).hexdigest()
            model = _existing_model(root, reference, profile)
            origin = "activity-cache"
        else:
            model = profile.load()
            origin = "temporal-activity"
    result = classify_batch(
        batch.manifest,
        batch.manifest.parent,
        output,
        model,
        cast(Literal["frame", "tiles"], profile.kind),
        verified_existing_sha256=reference["sha256"] if external else None,
    )
    if result["manifest_sha256"] != batch.sha256:
        raise ValueError("Classifier source changed after closed-batch validation")
    actual = hashlib.sha256(read_owned_file(output, root, 128_000_000)).hexdigest()
    if external is not None and actual != reference["sha256"]:
        raise ValueError("Pinned classifier output changed during adoption")
    reference["sha256"] = actual
    return Computed(reference, origin)
