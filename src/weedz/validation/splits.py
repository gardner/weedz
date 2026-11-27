"""A stable development / held-out split from a hash of each item's source ID."""

import hashlib
from typing import Literal

Split = Literal["development", "held-out"]
SALT = "weedz-validation-v1"


def split_of(item: str, *, salt: str = SALT, held_out: float = 0.5) -> Split:
    """Tune thresholds on `development` only; report `held-out`. Keep the salt fixed."""
    if not 0 < held_out < 1:
        raise ValueError("The held-out share must be between zero and one")
    digest = hashlib.sha256(f"{salt}:{item}".encode()).digest()
    position = int.from_bytes(digest[:8], "big") / 2**64
    return "held-out" if position < held_out else "development"
