"""Supported human controls become typed claims, not readonly model evidence."""

from dataclasses import dataclass

from weedz.annotation.import_controls import Decisions, decisions
from weedz.annotation.import_geometry import Region, decode_region
from weedz.annotation.import_records import HumanRecord


@dataclass(frozen=True)
class Claims:
    record: HumanRecord
    decision: Decisions
    regions: tuple[Region, ...]


def parse_claims(
    record: HumanRecord, size: tuple[int, int], taxa: set[str], categories: set[str]
) -> Claims:
    declared = decisions(record.results, taxa, categories)
    regions = []
    for result in record.results:
        kind = result.get("type")
        if kind in {"rectanglelabels", "brushlabels"}:
            regions.append(decode_region(result, size, taxa | categories))
        elif kind == "textarea":
            if result.get("from_name") != "model_evidence" or result.get("to_name") != "image":
                raise ValueError("Unsupported human text control; no implicit taxonomy conversion")
            # This readonly field is model evidence even when copied into a human annotation.
        elif kind != "choices":
            raise ValueError("Unsupported human annotation control")
    if len({region.id for region in regions}) != len(regions):
        raise ValueError("Duplicate human region identity")
    return Claims(record, declared, tuple(regions))
