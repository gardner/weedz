"""Keep source attribution portable when reading older capture manifests."""

from pathlib import PureWindowsPath
from typing import Any


def portable_credits(value: Any) -> Any:
    """Copy attribution records, reducing file references to platform-neutral names."""
    if isinstance(value, list):
        return [portable_credits(item) for item in value]
    if isinstance(value, dict):
        return {
            key: PureWindowsPath(item).name
            if key == "file" and isinstance(item, str)
            else portable_credits(item)
            for key, item in value.items()
        }
    return value
