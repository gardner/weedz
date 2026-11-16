"""Readonly JSON values for new review records; wire arrays remain JSON arrays."""

from collections.abc import Mapping
from types import MappingProxyType

from pydantic import JsonValue

type FrozenJson = (
    str | int | float | bool | None | tuple[FrozenJson, ...] | Mapping[str, FrozenJson]
)


def freeze_json(value: object) -> FrozenJson:
    """Copy nested containers so callers cannot mutate a validated review claim."""
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        return MappingProxyType({key: freeze_json(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("Review payload must contain JSON values")


def thaw_json(value: FrozenJson) -> JsonValue:
    """Explicit serialisation avoids leaking runtime proxies or converting arrays to objects."""
    if isinstance(value, Mapping):
        return {key: thaw_json(value[key]) for key in sorted(value)}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value
