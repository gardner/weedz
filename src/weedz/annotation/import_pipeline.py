"""Strict offline completed-human export import, with no Label Studio API writes."""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from weedz.annotation.gold_config import gold_config
from weedz.annotation.import_apply import apply_claims
from weedz.annotation.import_bindings import task_bindings
from weedz.annotation.import_claims import parse_claims
from weedz.annotation.import_package import Package, pinned_bytes, read_package
from weedz.annotation.import_records import completed_records, positive_id
from weedz.annotation.import_retractions import retract
from weedz.annotation.import_write import json_bytes, write_import
from weedz.contract import Sample
from weedz.manifest import manifest_bytes
from weedz.rights_profiles import (
    PUBLIC_PROFILE,
    RightsProfile,
    require_rights,
    rights_profile_fields,
)

# Integer RLE arrays expand substantially in the standard JSON decoder.
MAX_EXPORT_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class ImportInputs:
    package: Path
    package_sha256: str
    export: Path
    export_sha256: str
    config: Path
    config_sha256: str
    namespace: str
    project_id: int
    taxa: tuple[str, ...]
    categories: tuple[str, ...] = ()
    rights_profile: RightsProfile = PUBLIC_PROFILE


def _prior(
    request: ImportInputs, base: Package, previous: Path | None, checksum: str | None
) -> Package:
    if previous is None:
        if checksum is not None:
            raise ValueError("Previous package SHA needs its directory")
        return base
    if checksum is None:
        raise ValueError("Previous import requires its manifest SHA")
    prior = read_package(previous, checksum)
    receipt = json.loads(pinned_bytes(previous / "manifest.json", checksum))
    if (receipt.get("project_namespace"), receipt.get("project_id")) != (
        request.namespace,
        request.project_id,
    ):
        raise ValueError("Previous import came from a different source project")
    if receipt.get("source_package_sha256") != request.package_sha256:
        raise ValueError("Previous import has a different source package")
    _same_samples(base, prior)
    return prior


def _human_tasks(encoded: bytes, base: Package, project_id: int) -> list[tuple[str, dict]]:
    positive_id(project_id)
    tasks = json.loads(encoded)
    if not isinstance(tasks, list) or len(tasks) > 1000:
        raise ValueError("Use a full bounded Label Studio task export")
    selected = []
    seen = set()
    task_ids: set[int] = set()
    for task in tasks:
        if not isinstance(task, dict) or task.get("project") != project_id:
            raise ValueError("Export project identity mismatch")
        task_id = positive_id(task.get("id"))
        if task_id in task_ids:
            raise ValueError("duplicate numeric task identity in export")
        task_ids.add(task_id)
        key = task.get("meta", {}).get("external_id")
        if key not in base.samples or key in seen:
            raise ValueError("Unknown or duplicate external task identity")
        seen.add(key)
        if task.get("data", {}).get("image") != base.tasks[key]["data"]["image"]:
            raise ValueError("Export image identity differs from original task")
        selected.append((key, task))
    return selected


def _apply(
    tasks: list[tuple[str, dict]],
    samples: dict[str, Sample],
    request: ImportInputs,
    evidence: dict[str, str],
) -> tuple[dict[str, Sample], dict[str, bytes], int]:
    changed = dict(samples)
    masks = {}
    revisions = 0
    for key, task in tasks:
        sample = changed[key]
        if sample.media.width is None or sample.media.height is None:
            raise ValueError("Human review needs original image geometry")
        size = (sample.media.width, sample.media.height)
        known = frozenset(
            str(event.payload.get("annotation_revision_key")) for event in sample.review_history
        )
        for record in completed_records(task, request.namespace, known_cancelled_keys=known):
            before = len(sample.review_history)
            if record.cancelled:
                sample = retract(sample, record, evidence)
                revisions += len(sample.review_history) - before
                continue
            claims = parse_claims(
                record,
                size,
                set(request.taxa),
                set(request.categories),
            )
            before = len(sample.review_history)
            sample, new_masks = apply_claims(sample, claims, evidence, set(request.categories))
            revisions += len(sample.review_history) - before
            masks.update(new_masks)
        changed[key] = sample
    return changed, masks, revisions


def import_reviews(
    request: ImportInputs,
    output: Path,
    *,
    previous: Path | None = None,
    previous_sha256: str | None = None,
) -> dict:
    base = read_package(request.package, request.package_sha256)
    if base.human_import:
        raise ValueError(
            "A reviewed import cannot be a fresh source; "
            "retain the original package and use --previous"
        )
    prior = _prior(request, base, previous, previous_sha256)
    _admit(request, base, prior)
    config = pinned_bytes(request.config, request.config_sha256, 1024 * 1024)
    if config != gold_config(request.taxa, request.categories).encode("utf-8"):
        raise ValueError("Configuration is not the declared opt-in human review schema")
    exported = pinned_bytes(request.export, request.export_sha256, MAX_EXPORT_BYTES)
    evidence = {
        "export_sha256": request.export_sha256,
        "config_sha256": request.config_sha256,
        "source_package_sha256": request.package_sha256,
    }
    selected = _human_tasks(exported, base, request.project_id)
    history = (
        _historical_tasks(raw, base, request.project_id)
        for name, raw in prior.files.items()
        if prior is not base and name.startswith("private/exports/") and name.endswith(".json")
    )
    bindings = task_bindings(prior, selected, history)
    changed, masks, count = _apply(selected, prior.samples, request, evidence)
    files = {**prior.files, **masks}
    original = base.files["private/provenance.json"]
    files[f"private/source-provenance/{hashlib.sha256(original).hexdigest()}.json"] = original
    files[f"private/exports/{request.export_sha256}.json"] = exported
    files[f"private/configs/{request.config_sha256}.xml"] = config
    files["samples.jsonl"] = manifest_bytes(changed.values())
    files["private/provenance.json"] = json_bytes(
        {
            "samples": [
                {"external_id": key, "sample": sample.model_dump(mode="json")}
                for key, sample in changed.items()
            ]
        }
    )
    return write_import(
        request.package,
        output,
        files,
        dict(
            schema_version=1,
            source_package_sha256=request.package_sha256,
            export_sha256=request.export_sha256,
            config_sha256=request.config_sha256,
            project_namespace=request.namespace,
            project_id=request.project_id,
            imported_revisions=count,
            task_bindings=bindings,
            contract_schema_version=max(sample.schema_version for sample in changed.values()),
            **rights_profile_fields(request.rights_profile),
            interpretation=(
                "Completed human declarations; expertise and gold acceptance are separate"
            ),
        ),
    )


def _admit(request: ImportInputs, base: Package, prior: Package) -> None:
    for sample in base.samples.values():
        require_rights(sample, request.rights_profile)
    if base.rights_profile is not None and base.rights_profile != request.rights_profile:
        raise ValueError("Source package rights profile must be preserved")
    if prior is not base and (prior.rights_profile or PUBLIC_PROFILE) != request.rights_profile:
        raise ValueError("Previous import rights profile must be preserved")


def _same_samples(base: Package, prior: Package) -> None:
    if prior.samples.keys() != base.samples.keys():
        raise ValueError("Previous sample set differs")
    ignored = {"annotations", "completeness", "review_history", "schema_version"}
    for key, sample in base.samples.items():
        if prior.samples[key].schema_version < sample.schema_version:
            raise ValueError("Previous import cannot downgrade the source schema version")
        if sample.model_dump(exclude=ignored) != prior.samples[key].model_dump(exclude=ignored):
            raise ValueError("Previous import changed original sample identity or rights")


def _historical_tasks(raw: bytes, base: Package, project_id: int) -> list[tuple[str, dict]]:
    if len(raw) > MAX_EXPORT_BYTES:
        raise ValueError("Historical human export exceeds the pre-decode resource cap")
    return _human_tasks(raw, base, project_id)
