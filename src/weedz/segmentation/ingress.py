"""Explicit encoded-input budgets; historical proposal identities omit this extension."""

from copy import deepcopy

from weedz.segmentation.regions import MAX_SOURCE_BYTES, MAX_SOURCE_PIXELS

MAX_CANONICAL_BYTES = 160_000_000


def source_budget(maximum: int | None) -> int:
    if maximum is None:
        return MAX_SOURCE_BYTES
    if type(maximum) is not int or not 1 <= maximum <= MAX_CANONICAL_BYTES:
        raise ValueError("Source byte budget must be an integer in [1, 160000000]")
    return maximum


def proposal_metadata(metadata: dict, maximum: int | None) -> dict:
    result = deepcopy(metadata)
    if maximum is not None:
        if "source_ingress" in result:
            raise ValueError("Source ingress policy is reserved for the batch input budget")
        result["source_ingress"] = {
            "revision": 1,
            "max_source_bytes": source_budget(maximum),
            "max_source_pixels": MAX_SOURCE_PIXELS,
            "resize": "none; existing proposal model thumbnail policy unchanged",
        }
    return result
