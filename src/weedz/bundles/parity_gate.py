"""Validate recorded parity measurements rather than trusting a summary flag."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from weedz.discovery.parity import THRESHOLDS


class Measurement(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    value: float = Field(ge=0)
    limit: float = Field(ge=0)
    passed: bool


class ParityResult(BaseModel):
    # The benchmark also carries descriptive readouts, which are not gate inputs.
    model_config = ConfigDict(strict=True)

    passed: bool
    checks: dict[str, Measurement]


def validate_parity(value: Any) -> None:
    result = ParityResult.model_validate(value)
    limits = THRESHOLDS["limits"]
    if not result.passed or result.checks.keys() != limits.keys():
        raise ValueError("Parity requires every current check and a passing summary")
    for name, check in result.checks.items():
        if check.limit != limits[name] or not check.passed or check.value > limits[name]:
            raise ValueError(f"Parity check {name} does not pass the current limit")
        if name != "max_margin_drift" and not check.value.is_integer():
            raise ValueError(f"Parity check {name} must record an integer count")
