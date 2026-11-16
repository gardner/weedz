"""Only receipt-proven export snapshots confer importer replay authority."""

import hashlib
import re

from weedz.annotation.import_package import Package


def _sha(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Invalid owned export checksum")
    return value


def _legacy_anchors(base: Package, prior: Package, namespace: str) -> set[str]:
    owned = {_sha(prior.export_sha256)}
    for key, sample in prior.samples.items():
        source_events = {event.id for event in base.samples[key].review_history}
        for event in sample.review_history:
            revision_key = event.payload.get("annotation_revision_key")
            if (
                event.id not in source_events
                and event.origin == "reviewer"
                and event.action in {"completed_human_revision", "retracted_human_annotation"}
                and event.evidence.get("source_package_sha256") == base.sha256
                and isinstance(revision_key, str)
                and revision_key.startswith(f"label-studio:{namespace}:task:")
            ):
                owned.add(_sha(event.evidence.get("export_sha256")))
    return owned


def _legacy_complete(prior: Package, owned: set[str]) -> None:
    if prior.task_bindings is not None:
        return  # The pinned complete table preserves earlier zero-human task IDs.
    paths = {f"private/exports/{checksum}.json" for checksum in owned}
    if any(
        name.startswith("private/exports/") and name.endswith(".json") and name not in paths
        for name in prior.files
    ):
        raise ValueError("Legacy receipt has unproven export ownership; no history was guessed")


def historical_exports(base: Package, prior: Package, namespace: str) -> dict[str, bytes]:
    if prior is base:
        return {}
    current = _sha(prior.export_sha256)
    lineage = prior.owned_export_sha256
    if lineage is None:
        owned = _legacy_anchors(base, prior, namespace)
        _legacy_complete(prior, owned)
    else:
        if not isinstance(lineage, list) or not 1 <= len(lineage) <= 10_000:
            raise ValueError("Invalid owned export lineage")
        owned = {_sha(checksum) for checksum in lineage}
        if len(owned) != len(lineage) or current not in owned:
            raise ValueError("Owned export lineage omits its current snapshot or repeats entries")
    snapshots = {}
    for checksum in sorted(owned):
        raw = prior.files.get(f"private/exports/{checksum}.json")
        if raw is None or hashlib.sha256(raw).hexdigest() != checksum:
            raise ValueError("Missing or changed owned export snapshot")
        snapshots[checksum] = raw
    return snapshots
