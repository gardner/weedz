"""Represent invalid legacy result numbers honestly without weakening model-pin hashes."""

import json
import math
from typing import Any

NONFINITE_POLICY = "Invalid non-finite result numbers are serialized as null, never finite scores"


def _finite_results(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _finite_results(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite_results(item) for item in value]
    return value


def result_json(value: Any) -> str:
    """For result evidence/provenance only; model version hashing remains strict."""
    return json.dumps(_finite_results(value), ensure_ascii=False, allow_nan=False)
