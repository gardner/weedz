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
    "A photo counts as a found weed if any auditor's blind finding names a species; "
    "'disputed' counts photos where auditors' findings differ. Only an auditor's "
    "first answer counts, and only if nobody reviewed the photo before it without "
    "auditing it first; other audits are not blind and are left out of every count "
    "except 'not_blind', the photos that have such an audit. There is no "
    "calibrated detection threshold yet, so each found weed reports its 1-based rank in "
    "the incidental queue (by margin, highest first) and whether the found species was "
    "the top suggestion shown, rather than a hit or miss verdict. With a small sample, "
    "these counts bound rather than estimate how often screening ranks weeds low."
)


def audit_sample(run_id: str, photos: list[dict[str, Any]], fraction: float = FRACTION) -> set[str]:
    incidental = [photo["id"] for photo in photos if photo["cohort"] == "incidental"]
    if not incidental:
        return set()
    order = sorted(incidental, key=lambda pid: hashlib.sha256(f"{run_id}|{pid}".encode()).digest())
    return set(order[: max(1, math.ceil(len(order) * fraction))])


def queue_ranks(photos: list[dict[str, Any]]) -> dict[str, int]:
    """1-based positions in the incidental queue, ordered as the review app orders it."""
    incidental = [photo for photo in photos if photo["cohort"] == "incidental"]
    queue = sorted(incidental, key=lambda photo: -photo["scores"].get("margin", -2))
    return {photo["id"]: rank for rank, photo in enumerate(queue, start=1)}


def summarize_audit(
    photos: list[dict[str, Any]],
    sample: set[str],
    latest: dict[str, dict[str, str]],
    late: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Summarise blind audits (`latest`); `late` holds audits made after a review."""
    by_id = {photo["id"]: photo for photo in photos}
    ranks = queue_ranks(photos)
    audited = {pid: latest[pid] for pid in sorted(sample) if latest.get(pid)}
    findings = [
        {
            "photo_id": pid,
            "species": species,
            "top_suggestion": species == by_id[pid]["scores"].get("best_species"),
            "queue_rank": ranks[pid],
            "queue_size": len(ranks),
        }
        for pid, by_auditor in audited.items()
        for species in sorted(set(by_auditor.values()) & set(SPECIES))
    ]
    found = {finding["photo_id"] for finding in findings}
    as_top = {finding["photo_id"] for finding in findings if finding["top_suggestion"]}
    return {
        "meaning": MEANING,
        "fraction": FRACTION,
        "sampled": len(sample),
        "audited": len(audited),
        "remaining": len(sample) - len(audited),
        "weed_found": len(found),
        "found_as_top_suggestion": len(as_top),
        "found_not_top_suggestion": len(found - as_top),
        "not_blind": len(sample & set(late)),
        "disputed": sum(len(set(by_auditor.values())) > 1 for by_auditor in audited.values()),
        "unsure": sum("unsure" in by_auditor.values() for by_auditor in audited.values()),
        "findings": findings,
    }
