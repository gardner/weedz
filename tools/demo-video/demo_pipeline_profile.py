"""Semantic model pins for this fixed film, excluding machine/runtime versions."""

import hashlib
import json
from pathlib import Path

PROFILE_BYTES = Path(__file__).with_name("pipeline-profile.json").read_bytes()
FILM_PROFILE = json.loads(PROFILE_BYTES)
PROFILE_SHA256 = hashlib.sha256(PROFILE_BYTES).hexdigest()


def matches_recorded(actual: object, expected: object) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and matches_recorded(actual[key], value)
            for key, value in expected.items()
        )
    return type(actual) is type(expected) and actual == expected


def validate_recorded_profile(proof: dict) -> None:
    baseline = proof.get("baseline")
    nested = baseline.get("proposal_experiment") if isinstance(baseline, dict) else None
    for label, actual, expected in (
        ("baseline", baseline, FILM_PROFILE["baseline"]),
        ("proposer", proof.get("segmentation"), FILM_PROFILE["segmentation"]),
        ("baseline proposer", nested, FILM_PROFILE["segmentation"]),
    ):
        if not matches_recorded(actual, expected):
            raise ValueError(f"Capture does not match the film's recorded {label} recipe")
