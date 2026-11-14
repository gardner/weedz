"""A blind, rank-independent audit sample: the only way to see what screening misses.

The sample is derived from run and photo ids alone, so it is reproducible, cannot be
re-rolled, and gives low-ranked photos the same chance as high-ranked ones.
"""

import hashlib
import math
from typing import Any

from weedz.discovery.records import SPECIES

FRACTION = 0.25
MEANING = (
    "Blind audit of a fixed random sample of incidental photos, without the screening "
    "suggestion. Findings are reviewer judgements, not expert-verified identifications. "
    "With a small sample, missed counts bound rather than estimate the miss rate."
)


def audit_sample(run_id: str, photos: list[dict[str, Any]], fraction: float = FRACTION) -> set[str]:
    incidental = [photo["id"] for photo in photos if photo["cohort"] == "incidental"]
    if not incidental:
        return set()
    order = sorted(incidental, key=lambda pid: hashlib.sha256(f"{run_id}|{pid}".encode()).digest())
    return set(order[: max(1, math.ceil(len(order) * fraction))])


def _flagged(photo: dict[str, Any], species: str) -> bool:
    rows = photo.get("scores", {}).get("species", [])
    return any(row["name"] == species and row["margin"] > 0 for row in rows)


def summarize_audit(
    photos: list[dict[str, Any]], sample: set[str], latest: dict[str, str]
) -> dict[str, Any]:
    by_id = {photo["id"]: photo for photo in photos}
    audited = {pid: latest[pid] for pid in sample if pid in latest}
    found = {pid: finding for pid, finding in audited.items() if finding in SPECIES}
    flagged = sum(_flagged(by_id[pid], finding) for pid, finding in found.items())
    return {
        "meaning": MEANING,
        "fraction": FRACTION,
        "sampled": len(sample),
        "audited": len(audited),
        "remaining": len(sample) - len(audited),
        "weed_found": len(found),
        "flagged_by_screening": flagged,
        "missed_by_screening": len(found) - flagged,
        "unsure": sum(finding == "unsure" for finding in audited.values()),
    }
