"""Canonical JSON: the same manifest always gives the same bytes, and so the same hash.

Keys are sorted, there is no whitespace, text is UTF-8. Only values every JSON library
encodes identically are allowed: strings, booleans, null, lists, objects with ASCII keys
(sorted the same by code point and by UTF-16 unit, as RFC 8785 sorts), and integers a
double can hold exactly. Floats are refused, as their shortest form differs by language.
"""

import json
from typing import Any

SAFE_INTEGER = 2**53 - 1


def _check_object(value: dict, where: str) -> None:
    for key, item in value.items():
        if not isinstance(key, str) or not key.isascii():
            raise ValueError(f"{where}: object keys must be ASCII strings, not {key!r}")
        _check(item, f"{where}.{key}")


def _check(value: Any, where: str) -> None:
    if isinstance(value, dict):
        _check_object(value, where)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check(item, f"{where}[{index}]")
    elif isinstance(value, bool) or value is None or isinstance(value, str):
        return
    elif isinstance(value, int):
        if abs(value) > SAFE_INTEGER:
            raise ValueError(f"{where}: {value} is too large to round-trip through a double")
    else:
        raise ValueError(f"{where}: {type(value).__name__} has no canonical JSON form")


def canonical(value: Any) -> bytes:
    """The canonical UTF-8 JSON bytes of `value`, or ValueError if it has none."""
    _check(value, "$")
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")
