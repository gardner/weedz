"""Deterministic maximum-cardinality matching, not the COCO AP protocol.

Rows are labelled regions, columns are proposals in the fixed proposal-budget order.
Overlap descending then column order controls ties. Assignment never reads species.
"""

import math
from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Match:
    truth: int
    proposal: int
    overlap: float


@dataclass(frozen=True)
class Matching:
    matches: tuple[Match, ...]
    missed_truth: tuple[int, ...]
    unmatched_proposals: tuple[int, ...]


def _augment(
    start: int, edges: list[list[int]], assigned: dict[int, int], owners: dict[int, int]
) -> None:
    queue = deque([start])
    visited = {start}
    parents: dict[int, int] = {}
    while queue:
        truth = queue.popleft()
        for proposal in edges[truth]:
            if proposal in parents:
                continue
            parents[proposal] = truth
            if proposal not in owners:
                _assign(proposal, parents, assigned, owners)
                return
            owner = owners[proposal]
            if owner not in visited:
                visited.add(owner)
                queue.append(owner)


def _assign(
    proposal: int, parents: dict[int, int], assigned: dict[int, int], owners: dict[int, int]
) -> None:
    while True:
        truth = parents[proposal]
        previous = assigned.get(truth)
        assigned[truth] = proposal
        owners[proposal] = truth
        if previous is None:
            return
        proposal = previous


def match_regions(
    overlaps: Sequence[Sequence[float]], *, threshold: float, proposal_count: int | None = None
) -> Matching:
    """Maximise recovered labelled regions at a declared overlap threshold.

    Unmatched proposals are deliberately not called false positives: that requires
    an independently documented exhaustive label scope, assessed by the caller.
    """
    if not math.isfinite(threshold) or not 0 < threshold <= 1:
        raise ValueError("Overlap threshold must be in (0, 1]")
    columns = len(overlaps[0]) if overlaps else (proposal_count or 0)
    if proposal_count is not None and columns != proposal_count:
        raise ValueError("Proposal count disagrees with overlap matrix")
    if min(len(overlaps), columns) < 0 or max(len(overlaps), columns) > 1000:
        raise ValueError("Matching supports at most 1000 regions per side")
    edges = _edges(overlaps, columns, threshold)
    assigned: dict[int, int] = {}
    owners: dict[int, int] = {}
    for truth in range(len(overlaps)):
        _augment(truth, edges, assigned, owners)
    return Matching(
        tuple(
            Match(truth, proposal, overlaps[truth][proposal])
            for truth, proposal in sorted(assigned.items())
        ),
        tuple(truth for truth in range(len(overlaps)) if truth not in assigned),
        tuple(proposal for proposal in range(columns) if proposal not in owners),
    )


def _edges(overlaps: Sequence[Sequence[float]], columns: int, threshold: float) -> list[list[int]]:
    edges: list[list[int]] = []
    for row in overlaps:
        if len(row) != columns or any(
            not math.isfinite(value) or not 0 <= value <= 1 for value in row
        ):
            raise ValueError("Need a rectangular finite overlap matrix in [0, 1]")
        eligible = [column for column, value in enumerate(row) if value >= threshold]
        edges.append(sorted(eligible, key=lambda column: (-row[column], column)))
    return edges
