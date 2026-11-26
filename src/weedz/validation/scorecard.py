"""One result per check, collected into a scorecard with a Markdown table."""

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from weedz.validation.metrics import Rate

Sha256 = str


class CheckResult(BaseModel):
    """What one check measured, on which split, from which hashed inputs."""

    model_config = ConfigDict(frozen=True)

    check: str = Field(min_length=1)
    stage: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    split: str = Field(min_length=1)
    metrics: list[Rate]
    limits: list[str] = []
    inputs: dict[str, Sha256] = {}
    configuration: dict[str, str | int | float | bool] = {}
    seconds: float | None = None


class Scorecard(BaseModel):
    model_config = ConfigDict(frozen=True)

    created: datetime
    results: list[CheckResult]

    @classmethod
    def collect(cls, results: list[CheckResult]) -> "Scorecard":
        names = [result.check for result in results]
        if len(set(names)) != len(names):
            raise ValueError("Each check may appear once in a scorecard")
        ordered = sorted(results, key=lambda result: (result.stage, result.check))
        return cls(created=datetime.now(UTC), results=ordered)

    def write(self, path: Path) -> None:
        path.write_text(self.model_dump_json(indent=2) + "\n")

    @classmethod
    def read(cls, path: Path) -> "Scorecard":
        return cls.model_validate_json(path.read_text())

    def markdown(self) -> str:
        rows = [
            "| Stage | Check | Dataset | Split | Metric | Stratum | Count | Rate (95% CI) | Gate |",
            "| --- | --- | --- | --- | --- | --- | ---: | --- | --- |",
        ]
        for result in self.results:
            for metric in result.metrics:
                rows.append(
                    f"| {result.stage} | {result.check} | {result.dataset} | {result.split} "
                    f"| {metric.name} | {metric.stratum} | {metric.successes}/{metric.total} "
                    f"| {_interval(metric)} | {_gate(metric)} |"
                )
        return "\n".join(rows) + "\n"


def _interval(metric: Rate) -> str:
    if metric.value is None or metric.low is None or metric.high is None:
        return "unmeasured"
    return f"{metric.value:.1%} ({metric.low * 100:.1f}–{metric.high:.1%})"


def _gate(metric: Rate) -> str:
    if metric.passed is None:
        return "—"
    bound = f"≥ {metric.target:.0%}" if metric.target is not None else f"≤ {metric.ceiling:.0%}"
    return f"{'pass' if metric.passed else 'fail'} ({bound})"
