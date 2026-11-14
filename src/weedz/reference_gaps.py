"""Coverage and gaps of a reference collection, from the fields its samples record.

Counts are photos with an eligible example of the species, by source, label, view,
season and region. A dimension nobody records is stated as unknown or not recorded,
never as a gap: an iNaturalist photo's view is unknown, and no source or review step
records growth stage or habitat.
"""

from collections import Counter
from collections.abc import Iterable, Sequence
from typing import Any

from weedz.discovery.sampling import SEASONS

Example = dict[str, Any]
Cell = dict[str, Any]
NOT_RECORDED = {
    "growth_stage": "Growth stage is not recorded by any source or review step, so the "
    "collection cannot show gaps by growth stage",
    "habitat": "Habitat is not recorded by any source or review step, so the collection "
    "cannot show gaps by habitat",
}
# Dimensions with a fixed set of values; the others are compared with the values the
# collection itself holds (its sources and regions).
FIXED: dict[str, tuple[str, ...]] = {
    "view": ("nadir", "oblique", "ground"),
    "season": tuple(SEASONS),
}
DIMENSIONS = ("source", "region", "view", "season")
# Uses that need negatives and a spread of conditions; sharing needs only an example.
MODELLING = ("training", "evaluation")


def _value(example: Example, dimension: str) -> str:
    return example[dimension] or "unknown"


def _cell(examples: list[Example]) -> Cell:
    """Photos per value of each dimension; several examples on one photo count it once."""
    photos = {(example["sample_id"], example["label"]): example for example in examples}
    labels = Counter(label for _, label in photos)
    unique = {example["sample_id"]: example for example in examples}.values()
    counted = {
        f"by_{dimension}": dict(sorted(Counter(_value(item, dimension) for item in unique).items()))
        for dimension in DIMENSIONS
    }
    return {"photos": len(unique), "by_label": dict(sorted(labels.items()))} | counted


def coverage(
    examples: list[Example], uses: Sequence[str], expected: Iterable[str] = ()
) -> dict[str, dict[str, Cell]]:
    """Per species (declared or seen) and use, the photos with an eligible example."""
    species = sorted({*expected, *(item["taxon"] for item in examples if item["taxon"])})
    return {
        taxon: {
            use: _cell(
                [
                    item
                    for item in examples
                    if item["taxon"] == taxon and item["uses"][use]["eligible"]
                ]
            )
            for use in uses
        }
        for taxon in species
    }


def _expected(examples: list[Example], dimension: str) -> tuple[str, ...]:
    if dimension in FIXED:
        return FIXED[dimension]
    return tuple(sorted({item[dimension] for item in examples if item[dimension]}))


def _spread(
    taxon: str, use: str, cell: Cell, examples: list[Example]
) -> tuple[list[str], list[str]]:
    """Gaps in the recorded dimensions of one species and use, and those not recorded."""
    gaps: list[str] = []
    unknowns: list[str] = []
    for dimension in DIMENSIONS:
        known = set(cell[f"by_{dimension}"]) - {"unknown"}
        if dimension in FIXED and not known:
            unknowns.append(
                f"{taxon}: {dimension} is not recorded for any example eligible for {use}"
            )
            continue
        missing = [value for value in _expected(examples, dimension) if value not in known]
        if missing:
            gaps.append(
                f"{taxon}: no example eligible for {use} from {dimension}: {', '.join(missing)}"
            )
    return gaps, unknowns


def _species_gaps(
    taxon: str, cells: dict[str, Cell], examples: list[Example]
) -> tuple[list[str], list[str]]:
    gaps: list[str] = []
    unknowns: list[str] = []
    for use, cell in cells.items():
        if not cell["photos"]:
            gaps.append(f"{taxon}: no example eligible for {use}")
            continue
        if use not in MODELLING:
            continue
        if not cell["by_label"].get("absent"):
            gaps.append(f"{taxon}: no absent (negative) example eligible for {use}")
        spread, unrecorded = _spread(taxon, use, cell, examples)
        gaps += spread
        unknowns += unrecorded
    return gaps, unknowns


def gaps(
    examples: list[Example], covered: dict[str, dict[str, Cell]]
) -> tuple[list[str], list[str]]:
    """What the collection lacks, and what it cannot tell because it is not recorded."""
    missing: list[str] = []
    unknowns: list[str] = []
    for taxon, cells in covered.items():
        found, unrecorded = _species_gaps(taxon, cells, examples)
        missing += found
        unknowns += unrecorded
    return missing, unknowns
