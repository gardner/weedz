"""Label-free ranking policies for same-model crop predictions, not calibration."""

from collections import Counter
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RankedTaxon(BaseModel):
    """One uncalibrated closed-set prediction from the recorded classifier."""

    model_config = ConfigDict(frozen=True)

    taxon: str = Field(min_length=1)
    score: float = Field(ge=0, le=1, allow_inf_nan=False)
    score_kind: Literal["closed_set_softmax_uncalibrated"]


def aggregate_taxa(
    crops: Sequence[Sequence[RankedTaxon]], *, policy: str, budget: int
) -> list[str]:
    """Rank all candidate taxa before truncation; ties retain first encounter order.

    Frequency counts one vote per crop. Max-score retains the strongest individual
    crop score for each taxon. Both are heuristics; neither creates a calibrated
    species-presence probability or restricts predictions to ground-truth taxa.
    Only compare scores from a single recorded model and score scale.
    """
    if type(budget) is not int or budget < 1:
        raise ValueError("The final taxon budget must be a positive integer")
    if policy not in {"frequency", "max_score"}:
        raise ValueError(f"Unknown aggregation policy: {policy}")
    votes: Counter[str] = Counter()
    maxima: dict[str, float] = {}
    for crop in crops:
        taxa = [prediction.taxon for prediction in crop]
        if len(set(taxa)) != len(taxa):
            raise ValueError("Duplicate taxon within one crop ranking")
        votes.update(taxa)
        for prediction in crop:
            maxima[prediction.taxon] = max(maxima.get(prediction.taxon, 0), prediction.score)
    weights = votes if policy == "frequency" else maxima
    return sorted(weights, key=lambda taxon: -weights[taxon])[:budget]
