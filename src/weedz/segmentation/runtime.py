"""Trusted worker configuration for the pinned optional SAM activity runtime."""

import os
from pathlib import Path

from weedz.segmentation.regions import ProposalConfig
from weedz.segmentation.sam2 import CHECKPOINT_SHA256, Sam2Proposer


def load_proposer(root: Path) -> Sam2Proposer:
    checkpoint = os.environ.get("WEEDZ_SAM2_CHECKPOINT")
    if not checkpoint:
        raise ValueError("Configure WEEDZ_SAM2_CHECKPOINT before accepting segmented runs")
    device = os.environ.get("WEEDZ_SAM2_DEVICE", "cpu")
    if device not in {"cpu", "cuda:0"}:
        raise ValueError("SAM activity device must be cpu or the configured cuda:0")
    return Sam2Proposer(
        Path(checkpoint),
        CHECKPOINT_SHA256,
        root / "segmentation-cache-v1",
        ProposalConfig(),
        device,
    )
