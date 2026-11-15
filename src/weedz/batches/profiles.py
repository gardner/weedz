"""Explicit inference profiles: inspecting cache provenance never loads a GPU model."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from weedz.annotation.semantic import CLASSIFIER_FIELDS, CONFIG_FIELDS, PROPOSER_FIELDS
from weedz.batches.contract import PROFILE

Kind = Literal["proposals", "frame", "tiles", "regions"]


def _fields(metadata: dict, names: tuple[str, ...]) -> dict:
    if any(name not in metadata or metadata[name] is None for name in names):
        raise ValueError("Incomplete registered model profile metadata")
    return {name: metadata[name] for name in names}


def sam_identity(metadata: dict) -> dict:
    selected = _fields(metadata, PROPOSER_FIELDS)
    config = metadata.get("proposal_config")
    if not isinstance(config, dict) or not CONFIG_FIELDS.issubset(config):
        raise ValueError("Incomplete registered proposal profile configuration")
    return {**selected, "proposal_config": config}


def model_identity(metadata: dict, kind: Kind) -> dict:
    if kind == "proposals":
        return sam_identity(metadata)
    selected = _fields(metadata, (*CLASSIFIER_FIELDS, "input_policy"))
    if kind == "tiles":
        selected.update(_fields(metadata, ("aggregation", "ranking_revision")))
    elif kind == "regions":
        selected["proposer"] = sam_identity(metadata.get("proposer", {}))
    elif kind != "frame":
        raise ValueError("Unknown registered inference profile kind")
    return selected


@dataclass(frozen=True)
class ModelProfile:
    name: str
    kind: Kind
    metadata: dict[str, Any]
    loader: Callable[[], Any] = field(repr=False, compare=False)
    identity: Callable[[dict, Kind], dict] = field(
        default=model_identity, repr=False, compare=False
    )
    _semantic: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if PROFILE.fullmatch(self.name) is None:
            raise ValueError("Choose a versioned registered model profile name")
        # Freeze a canonical snapshot so later mutation of input dictionaries cannot alter pins.
        encoded = json.dumps(
            self.identity(self.metadata, self.kind), sort_keys=True, allow_nan=False
        )
        object.__setattr__(self, "_semantic", encoded)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self._semantic.encode()).hexdigest()

    def matches(self, metadata: dict) -> bool:
        encoded = json.dumps(self.identity(metadata, self.kind), sort_keys=True, allow_nan=False)
        return encoded == self._semantic

    def load(self) -> Any:
        model = self.loader()
        if not self.matches(model.metadata):
            raise ValueError("Loaded model disagrees with its registered inference profile")
        return model
