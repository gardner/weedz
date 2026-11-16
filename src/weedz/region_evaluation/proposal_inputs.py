"""Checksum-bound proposal inputs; label revisions never rewrite inference provenance."""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from weedz.contract import Sample


@dataclass(frozen=True)
class ProposalBatch:
    ready_sha256: str
    manifest_sha256: str
    proposals_sha256: str
    model_version: str
    rows: dict[str, dict]


def _pinned(path: Path, sha256: str, limit: int) -> bytes:
    with path.open("rb") as source:
        encoded = source.read(limit + 1)
    if len(encoded) > limit or hashlib.sha256(encoded).hexdigest() != sha256:
        raise ValueError("Proposal input checksum mismatch or resource cap exceeded")
    return encoded


def load_proposals(ready: Path, sha256: str, samples: Sequence[Sample]) -> ProposalBatch:
    """Join exact image identities, allowing independently versioned label manifests.

    The original inference manifest SHA remains in the result. It is not replaced by
    a later human/source-label revision's manifest SHA merely because pixels match.
    """
    header = json.loads(_pinned(ready, sha256, 1024 * 1024))
    if header.get("schema") != 1 or not isinstance(header.get("model_version"), str):
        raise ValueError("Unsupported closed proposal header")
    expected = {sample.id: sample for sample in samples}
    if not 1 <= len(expected) <= 1000 or len(expected) != len(samples):
        raise ValueError("Need unique bounded evaluation samples")
    if any(not sample.media.sha256 for sample in samples):
        raise ValueError("Evaluation media must be checksum-pinned")
    encoded = _pinned(
        ready.with_name("proposals.jsonl"), header["proposals_sha256"], 256 * 1024 * 1024
    )
    rows = [json.loads(line) for line in encoded.splitlines()]
    if len(rows) != len(samples) or header.get("count") != len(rows):
        raise ValueError("Proposal count differs from evaluation sample count")
    selected = _join(rows, expected, header["model_version"])
    return ProposalBatch(
        sha256,
        header["manifest_sha256"],
        header["proposals_sha256"],
        header["model_version"],
        selected,
    )


def _join(rows: list[dict], samples: dict[str, Sample], version: str) -> dict[str, dict]:
    selected: dict[str, dict] = {}
    for row in rows:
        key = row.get("sample_id")
        if key not in samples or key in selected:
            raise ValueError("Unknown or duplicate proposal sample identity")
        if row.get("image_sha256") != samples[key].media.sha256:
            raise ValueError("Proposal media identity differs from labelled source")
        if row.get("model_version") != version:
            raise ValueError("Proposal model identity differs from closed header")
        stage = row.get("segmentation", {})
        if stage.get("status") not in {"ok", "empty", "partial", "failed"}:
            raise ValueError("Unknown proposal execution status")
        if not isinstance(stage.get("regions"), list):
            raise ValueError("Missing proposal regions")
        selected[key] = row
    return selected
