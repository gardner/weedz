"""Standing-claim ownership comes from recorded revisions, never ID prefixes."""

from collections.abc import Mapping

from weedz.contract import ReviewEvent


def owned_ids(previous: ReviewEvent | None) -> tuple[set[str], set[str]]:
    if previous is None:
        return set(), set()
    annotations = previous.payload.get("annotations", ())
    if not isinstance(annotations, (list, tuple)):
        raise ValueError("Recorded revision annotations must be an array")
    ids = {str(item["id"]) for item in annotations if isinstance(item, Mapping) and "id" in item}
    coverage = previous.payload.get("completeness")
    completeness = {str(coverage["id"])} if isinstance(coverage, Mapping) else set()
    return ids, completeness
