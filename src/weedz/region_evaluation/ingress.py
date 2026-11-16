"""An evaluation decoder cannot relabel the stored model's input policy."""

from weedz.region_evaluation.proposal_inputs import ProposalBatch
from weedz.segmentation.ingress import ingress_identity, proposal_metadata


def validate_source_ingress(proposed: ProposalBatch, maximum: int | None) -> None:
    """Require exact policy identity, including historical absence vs explicit default."""
    requested = proposal_metadata({}, maximum)
    for row in proposed.rows.values():
        recorded = ingress_identity(row["segmentation"]["provenance"])
        if recorded != requested:
            raise ValueError("Evaluation source ingress differs from stored proposal provenance")
