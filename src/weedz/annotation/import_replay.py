"""Reconstruct prior human state only from ordered, receipt-owned captures."""

import hashlib
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from weedz.annotation.gold_config import gold_config
from weedz.annotation.import_assets import check_assets
from weedz.annotation.import_claims import PreparedClaims
from weedz.annotation.import_package import Package
from weedz.annotation.import_records import HumanRecord

if TYPE_CHECKING:
    from weedz.annotation.import_pipeline import ImportInputs

MAX_REPLAY_BRUSH_PIXELS = 2_000_000_000
MAX_REPLAY_VISITS = 100_000
MAX_CAPTURES = 10_000


@dataclass
class ReplayBudget:
    pixels: int = 0

    def reserve(self, jobs: list[tuple[str, PreparedClaims | HumanRecord]]) -> None:
        for _, prepared in jobs:
            if isinstance(prepared, PreparedClaims):
                self.pixels += sum(row.get("type") == "brushlabels" for row in prepared.rows) * (
                    prepared.size[0] * prepared.size[1]
                )
        if self.pixels > MAX_REPLAY_BRUSH_PIXELS:
            raise ValueError("Historical brush replay exceeds its decoded work budget")


def capture(request: "ImportInputs") -> dict:
    return dict(
        export_sha256=request.export_sha256,
        config_sha256=request.config_sha256,
        taxa=list(request.taxa),
        categories=list(request.categories),
    )


def _scopes(row: dict, name: str) -> tuple[str, ...]:
    values = row.get(name)
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ValueError("Invalid capture journal scope")
    return tuple(values)


def capture_journal(
    base: Package, prior: Package, request: "ImportInputs", owned: dict[str, bytes]
) -> list[dict]:
    if prior is base:
        return []
    journal = prior.capture_journal
    if journal is None:
        # A single capture has a provable order; require its actual archived configuration.
        if len(owned) != 1 or prior.config_sha256 != request.config_sha256:
            raise ValueError("Legacy import has no provable capture order/configuration")
        journal = [{**capture(request), "export_sha256": prior.export_sha256}]
    _journal_shape(journal)
    if {row.get("export_sha256") for row in journal} != set(owned):
        raise ValueError("Capture journal differs from receipt-owned exports")
    if (
        journal[-1].get("export_sha256") != prior.export_sha256
        or journal[-1].get("config_sha256") != prior.config_sha256
    ):
        raise ValueError("Capture journal differs from the latest receipt")
    return journal


def _journal_shape(journal: object) -> None:
    if not isinstance(journal, list) or not 1 <= len(journal) <= MAX_CAPTURES:
        raise ValueError("Invalid ordered capture journal")
    if any(not isinstance(row, dict) for row in journal):
        raise ValueError("Invalid capture journal entry")
    if any(not isinstance(row.get("export_sha256"), str) for row in journal):
        raise ValueError("Invalid capture journal export checksum")


def _captures(
    base: Package,
    prior: Package,
    request: "ImportInputs",
    owned: dict[str, bytes],
    journal: list[dict],
) -> list[tuple["ImportInputs", list[tuple[str, dict]]]]:
    from weedz.annotation.import_pipeline import _human_tasks

    captures = []
    parsed = {}
    visits = 0
    for row in journal:
        taxa, categories = _scopes(row, "taxa"), _scopes(row, "categories")
        config = gold_config(taxa, categories).encode("utf-8")
        config_sha = hashlib.sha256(config).hexdigest()
        if (
            len(config) > 1024 * 1024
            or row.get("config_sha256") != config_sha
            or prior.files.get(f"private/configs/{config_sha}.xml") != config
        ):
            raise ValueError("Capture journal configuration is not its archived canonical schema")
        checksum = row["export_sha256"]
        if checksum not in parsed:
            parsed[checksum] = _human_tasks(owned[checksum], base, request.project_id)
        tasks = parsed[checksum]
        for _, task in tasks:
            if not isinstance(task.get("annotations", []), list):
                raise ValueError("Historical annotation records must be a list")
            visits += 1 + len(task.get("annotations", []))
        if visits > MAX_REPLAY_VISITS:
            raise ValueError("Historical replay exceeds its task/record visit budget")
        captures.append(
            (
                replace(
                    request,
                    export_sha256=checksum,
                    config_sha256=config_sha,
                    taxa=taxa,
                    categories=categories,
                ),
                tasks,
            )
        )
    return captures


def validate_prior(
    base: Package,
    prior: Package,
    request: "ImportInputs",
    owned: dict[str, bytes],
    exported: bytes,
    config: bytes,
) -> tuple[list[dict], ReplayBudget]:
    from weedz.annotation.import_bindings import task_bindings
    from weedz.annotation.import_pipeline import _apply

    check_assets(base.samples.values(), prior.files, base.files)
    journal = capture_journal(base, prior, request, owned)
    if len(journal) >= MAX_CAPTURES:
        raise ValueError("Ordered capture journal exceeds its replay resource cap")
    prospective = replace(
        prior, files={**prior.files, f"private/configs/{request.config_sha256}.xml": config}
    )
    # Preflight the next closed chain too, so its output remains replayable.
    captures = _captures(
        base,
        prospective,
        request,
        {**owned, request.export_sha256: exported},
        [*journal, capture(request)],
    )[:-1]
    actual_bindings = task_bindings(base, [], [tasks for _, tasks in captures])
    if prior.task_bindings is not None and actual_bindings != prior.task_bindings:
        raise ValueError("Recorded task bindings differ from reconstructed human state")
    state = dict(base.samples)
    budget = ReplayBudget()
    for historical, tasks in captures:
        evidence = dict(
            export_sha256=historical.export_sha256,
            config_sha256=historical.config_sha256,
            source_package_sha256=base.sha256,
        )
        state, masks, _ = _apply(tasks, state, historical, evidence, base.samples, budget)
        if any(prior.files.get(name) != raw for name, raw in masks.items()):
            raise ValueError("Historical human mask differs from its reconstructed human state")
    if any(
        state[key].model_dump(mode="json") != sample.model_dump(mode="json")
        for key, sample in prior.samples.items()
    ):
        raise ValueError("Previous import differs from reconstructed human state")
    return journal, budget
