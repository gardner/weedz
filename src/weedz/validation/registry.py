"""Checks register here by name; the CLI runs them with a shared context."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from weedz.validation.scorecard import CheckResult


@dataclass(frozen=True)
class RunContext:
    """Where public data and caches live, and an optional item limit for smoke runs."""

    data_root: Path
    cache_dir: Path
    device: str = "cpu"
    limit: int | None = None


@dataclass(frozen=True)
class Check:
    name: str
    stage: str
    dataset: str
    run: Callable[[RunContext], CheckResult]
    description: str = ""


REGISTRY: dict[str, Check] = {}


def register(check: Check) -> Check:
    if check.name in REGISTRY:
        raise ValueError(f"A check named {check.name} is already registered")
    REGISTRY[check.name] = check
    return check
