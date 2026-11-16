"""Preflight every human region and its work budget before materializing masks."""

from dataclasses import dataclass

from weedz.annotation.import_controls import Decisions, decisions
from weedz.annotation.import_geometry import Region, decode_region, region_geometry
from weedz.annotation.import_records import HumanRecord

MAX_REGIONS_PER_RECORD = 64
MAX_RECORD_BRUSH_PIXELS = 160_000_000
MAX_IMPORT_BRUSH_PIXELS = 400_000_000


@dataclass(frozen=True)
class Claims:
    record: HumanRecord
    decision: Decisions
    regions: tuple[Region, ...]


@dataclass(frozen=True)
class PreparedClaims:
    record: HumanRecord
    decision: Decisions
    rows: tuple[dict, ...]
    size: tuple[int, int]
    labels: frozenset[str]

    def decode(self) -> Claims:
        return Claims(
            self.record,
            self.decision,
            tuple(decode_region(row, self.size, set(self.labels)) for row in self.rows),
        )


@dataclass
class DecodeBudget:
    brush_pixels: int = 0

    def reserve(self, geometries: list[tuple[str, str, str, dict]], size: tuple[int, int]) -> None:
        if len(geometries) > MAX_REGIONS_PER_RECORD:
            raise ValueError("Human region count exceeds the record budget")
        pixels = sum(kind == "brushlabels" for kind, *_ in geometries) * size[0] * size[1]
        if pixels > MAX_RECORD_BRUSH_PIXELS or self.brush_pixels + pixels > MAX_IMPORT_BRUSH_PIXELS:
            raise ValueError("Human brush pixels exceed the decoded work budget")
        self.brush_pixels += pixels


def prepare_claims(
    record: HumanRecord,
    size: tuple[int, int],
    taxa: set[str],
    categories: set[str],
    budget: DecodeBudget,
    *,
    revision: int = 1,
) -> PreparedClaims:
    declared = decisions(record.results, taxa, categories, revision=revision)
    rows, geometries = [], []
    for result in record.results:
        kind = result.get("type")
        if kind in {"rectanglelabels", "brushlabels"}:
            geometries.append(region_geometry(result, size, taxa | categories))
            rows.append(result)
        elif kind == "textarea":
            if result.get("from_name") != "model_evidence" or result.get("to_name") != "image":
                raise ValueError("Unsupported human text control; no implicit taxonomy conversion")
        elif kind != "choices":
            raise ValueError("Unsupported human annotation control")
    if len({geometry[1] for geometry in geometries}) != len(geometries):
        raise ValueError("Duplicate human region identity")
    budget.reserve(geometries, size)
    return PreparedClaims(record, declared, tuple(rows), size, frozenset(taxa | categories))


def parse_claims(
    record: HumanRecord,
    size: tuple[int, int],
    taxa: set[str],
    categories: set[str],
    *,
    revision: int = 1,
) -> Claims:
    return prepare_claims(
        record, size, taxa, categories, DecodeBudget(), revision=revision
    ).decode()
