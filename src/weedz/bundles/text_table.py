"""The fixed prompts' text embeddings, computed once on the server for every device.

A phone runs only the image tower. It scores each window against this table, whose rows
follow `prompts()`: the watchlist targets first, then the comparison labels. The file is
raw little-endian float32, row-major, so any platform reads it without a parser; its
shape and prompts are in the manifest.
"""

import hashlib
from pathlib import Path
from typing import Any

import numpy as np

from weedz.discovery.inference import LABELS, MODELS, prompt
from weedz.discovery.records import SPECIES

DTYPE = "float32-le"


def prompts() -> list[str]:
    """The table's rows, in order."""
    return [prompt(label) for label in LABELS]


def table_bytes(embeddings: Any) -> bytes:
    """One float32 row per fixed prompt."""
    rows = np.asarray(embeddings, dtype="<f4")
    if rows.ndim != 2 or len(rows) != len(prompts()):
        raise ValueError(f"Expected {len(prompts())} embedding rows, got shape {rows.shape}")
    return rows.tobytes(order="C")


def table_entry(path: Path, model_key: str) -> dict[str, Any]:
    """How the manifest describes a table file, refusing one that does not fit the prompts."""
    data = path.read_bytes()
    rows = len(prompts())
    if not data or len(data) % (4 * rows):
        raise ValueError(f"{path} ({len(data)} bytes) does not fit {rows} prompts of float32")
    return {
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "dtype": DTYPE,
        "shape": [rows, len(data) // (4 * rows)],
        "prompts": prompts(),
        "target_count": len(SPECIES),
        "model_key": model_key,
        "model_revision": MODELS[model_key]["revision"],
        "normalised": True,
    }


def write_text_table(model_key: str, out: Path) -> dict[str, Any]:  # pragma: no cover - model
    """Embed the fixed prompts with the pinned model's text tower and write the table."""
    from weedz.discovery.inference import Screener

    screener = Screener.load(model=model_key)
    if screener.prompts != prompts():
        raise ValueError("The screener's prompts differ from the bundle's")
    out.write_bytes(table_bytes(screener.text.cpu().numpy()))
    return table_entry(out, model_key)
